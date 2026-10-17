"""Fatima's scoring/standings/fixtures services running inside the platform (HTTP, real Postgres)."""
import threading

import httpx

from app.core.signing import sign_record

SPORT = {"sport_id": "mystery-1", "name": "Mystery", "scoring_model": "event",
         "periods": {"count": 2, "duration_minutes": 10}, "scoring_events": {"zap": {"points": 7}},
         "draw_allowed": True, "overtime": {"policy": "none"},
         "roster": {"min_squad_size": 1, "max_squad_size": 5, "required_positions": {}}}


def ev(c, eid, mid, typ, payload=None):
    return c.post("/audit/v1/events", json={"event_id": eid, "match_id": mid, "type": typ, "payload": payload or {}})


def league(c, lid="lg-d1", teams=("a", "b"), spots=1):
    r = c.post("/audit/v1/leagues", json={"league_id": lid, "sport_id": "football", "teams": list(teams),
                                          "fixtures": [{"match_id": "dm", "home": teams[0], "away": teams[1]}],
                                          "qualification": {"spots": spots}})
    assert r.status_code == 201, r.text


def test_baseline_sports_are_data_and_reset_restores_them(client, reset):
    assert client.post("/audit/v1/sports", json=SPORT).status_code == 201
    reset()
    r = client.post("/audit/v1/sports", json=SPORT)
    assert r.status_code == 201                      # reset removed the earlier one; no conflict


def test_full_flow_signature_replay_score_standings(client, reset):
    league(client)
    assert ev(client, "d-1", "dm", "match_start").status_code == 201
    payload = {"team_id": "a", "event_type": "goal"}
    r = ev(client, "d-2", "dm", "score", payload)
    assert r.status_code == 201
    assert r.json()["signature"] == sign_record("d-2", payload, salt="demo-salt")
    again = ev(client, "d-2", "dm", "score", payload)
    assert again.status_code == 200 and again.json() == r.json()
    changed = ev(client, "d-2", "dm", "score", {"team_id": "b", "event_type": "goal"})
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "DUPLICATE_EVENT_ID"
    assert ev(client, "d-3", "dm", "match_end").status_code == 201
    assert client.get("/audit/v1/score/dm").json()["home"]["score"] == 1
    table = client.get("/audit/v1/standings/lg-d1").json()["table"]
    assert (table[0]["team_id"], table[0]["status"]) == ("a", "clinched")


def test_mystery_sport_scores_by_configuration(client, reset):
    assert client.post("/audit/v1/sports", json=SPORT).status_code == 201
    init = {"sport_id": "mystery-1", "home_team_id": "x", "away_team_id": "y"}
    assert ev(client, "q-0", "qm", "match_init", init).status_code == 201
    ev(client, "q-1", "qm", "match_start")
    assert ev(client, "q-2", "qm", "score", {"team_id": "x", "event_type": "zap"}).status_code == 201
    assert client.get("/audit/v1/score/qm").json()["home"]["score"] == 7
    bad = ev(client, "q-3", "qm", "score", {"team_id": "x", "event_type": "goal"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "UNKNOWN_EVENT_TYPE"


def test_errors_use_platform_shape_and_400_not_422(client, reset):
    for path, body in (("/audit/v1/events", {}), ("/audit/v1/sports", {}), ("/audit/v1/leagues", {})):
        r = client.post(path, json=body)
        assert r.status_code == 400 and set(r.json()["error"]) == {"code", "message", "details"}
    assert client.post("/audit/v1/events", content=b"{").status_code == 400
    assert client.get("/audit/v1/score/ghost").status_code == 404
    assert client.get("/audit/v1/standings/ghost").json()["error"]["code"] == "LEAGUE_NOT_FOUND"
    big = client.post("/audit/v1/fixtures", content=b"x" * (1024 * 1024 + 1))
    assert big.status_code == 413


def test_fixtures_are_pure_and_work(client, reset):
    r = client.post("/audit/v1/fixtures", json={"format": "round_robin", "teams": ["a", "b", "c", "d"]})
    assert r.status_code == 200 and r.json()


def test_compensation_rolls_back_score(client, reset):
    league(client, "lg-c")
    ev(client, "c-1", "dm", "match_start")
    ev(client, "c-2", "dm", "score", {"team_id": "a", "event_type": "goal"})
    assert ev(client, "c-3", "dm", "compensation", {"compensates": "c-2", "reason": "var"}).status_code == 201
    assert client.get("/audit/v1/score/dm").json()["home"]["score"] == 0
    assert ev(client, "c-4", "dm", "compensation", {"compensates": "c-2", "reason": "again"}).status_code == 409


def test_reset_clears_domain_state(client, reset):
    league(client, "lg-r")
    ev(client, "r-1", "dm", "match_start")
    reset()
    assert client.get("/audit/v1/score/dm").status_code == 404
    league(client, "lg-r")                                   # id is free again
    assert ev(client, "r-1", "dm", "match_start").status_code == 201


def test_concurrent_distinct_events_get_unique_sequences(client, server, reset):
    league(client, "lg-p")
    ev(client, "p-0", "dm", "match_start")
    out, barrier = [], threading.Barrier(12)

    def go(i):
        with httpx.Client(base_url=server, timeout=30) as c:
            barrier.wait()
            out.append(ev(c, f"p-{i + 1}", "dm", "score", {"team_id": "a", "event_type": "goal"}))
    ts = [threading.Thread(target=go, args=(i,)) for i in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert [r.status_code for r in out] == [201] * 12
    assert sorted(r.json()["sequence"] for r in out) == list(range(2, 14))
    assert client.get("/audit/v1/score/dm").json()["home"]["score"] == 12


# ------------------------------------------------------------- offline sync on the REAL scoring --
def act(aid, body, base, ts):
    return {"action_id": aid, "type": "score_event", "queued_at": ts, "base_version": base, "payload": body}


def test_offline_sync_with_real_scoring_end_to_end(client, reset):
    league(client, "lg-o")
    body = lambda e, t, p=None: {"event_id": e, "match_id": "dm", "type": t, "payload": p or {}}
    batch = [act("o3", body("o-3", "match_end"), 2, "2026-10-17T11:00:03Z"),
             act("o1", body("o-1", "match_start"), 0, "2026-10-17T11:00:01Z"),
             act("o2", body("o-2", "score", {"team_id": "a", "event_type": "goal"}), 1, "2026-10-17T11:00:02Z")]
    r = client.post("/audit/v1/offline-sync", json={"device_id": "dev", "actions": batch})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["summary"] == {"applied": 3, "rejected": 0, "duplicate": 0}
    assert [x["processed_order"] for x in out["results"]] == [3, 1, 2]
    assert out["results"][2]["signature"] == sign_record("o-2", {"team_id": "a", "event_type": "goal"}, salt="demo-salt")
    assert client.get("/audit/v1/score/dm").json()["home"]["score"] == 1
    again = client.post("/audit/v1/offline-sync", json={"device_id": "dev", "actions": batch}).json()
    assert again["summary"] == {"applied": 0, "rejected": 0, "duplicate": 3}
    # same event_id from another device: identical -> duplicate, different -> DUPLICATE_EVENT_ID
    same = client.post("/audit/v1/offline-sync", json={"device_id": "d2", "actions": [
        act("z1", body("o-2", "score", {"team_id": "a", "event_type": "goal"}), 3, "2026-10-17T12:00:00Z"),
        act("z2", body("o-2", "score", {"team_id": "b", "event_type": "goal"}), 3, "2026-10-17T12:00:01Z")]}).json()
    assert [x["status"] for x in same["results"]] == ["duplicate", "rejected"]
    assert same["results"][1]["error_code"] == "DUPLICATE_EVENT_ID"


def test_offline_real_scoring_rule_rejections(client, reset):
    league(client, "lg-o2")
    r = client.post("/audit/v1/offline-sync", json={"device_id": "dev", "actions": [
        act("a1", {"event_id": "x-1", "match_id": "dm", "type": "score",
                   "payload": {"team_id": "a", "event_type": "goal"}}, 0, "2026-10-17T11:00:00Z"),
        act("a2", {"event_id": "x-2", "match_id": "ghost", "type": "match_start", "payload": {}}, 0,
            "2026-10-17T11:00:01Z"),
        act("a3", {"event_id": "x-3", "match_id": "dm", "type": "match_start", "payload": {}}, 7,
            "2026-10-17T11:00:02Z")]}).json()
    assert [x["error_code"] for x in r["results"]] == ["MATCH_NOT_IN_PROGRESS", "MATCH_NOT_FOUND",
                                                        "INVALID_BASE_VERSION"]


# ------------------------------------------------------------------------------ mobile --------
def _tok(client, email):
    return {"Authorization": "Bearer " + client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Nascon@26"}).json()["token"]}


def test_mobile_reads_and_scoring_authorization(client, reset):
    league(client, "lg-m")
    viewer, admin = _tok(client, "viewer@nascon.test"), _tok(client, "admin@nascon.test")
    assert client.get("/api/v1/matches/dm").status_code == 401
    ev_body = {"event_id": "mm-1", "type": "match_start", "payload": {}}
    assert client.post("/api/v1/matches/dm/events", headers=viewer, json=ev_body).status_code == 403
    r = client.post("/api/v1/matches/dm/events", headers=admin, json=ev_body)
    assert r.status_code == 201 and r.json()["match_id"] == "dm"
    assert client.post("/api/v1/matches/dm/events", headers=admin, json={**ev_body, "match_id": "other"}).status_code == 400
    assert client.get("/api/v1/matches/dm", headers=viewer).json()["status"] == "in_progress"
    assert client.get("/api/v1/leagues/lg-m/standings", headers=viewer).status_code == 200
    assert client.get("/api/v1/leagues/ghost/standings", headers=viewer).status_code == 404
    assert client.post("/api/v1/fixtures/preview", headers=viewer,
                       json={"format": "single_elim", "teams": ["a", "b"]}).status_code == 200


def test_mobile_organizer_scoped_to_own_league(client, reset):
    league(client, "lg-x")                                    # audit league: no owner organizer
    org = _tok(client, "organizer@nascon.test")
    r = client.post("/api/v1/matches/dm/events", headers=org,
                    json={"event_id": "mo-1", "type": "match_start", "payload": {}})
    assert r.status_code == 403
