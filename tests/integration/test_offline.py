"""Offline sync coordinator (Section 5.14). Uses the in-memory scoring port stand-in, because the
real scoring engine belongs to the scoring owner; the coordinator only depends on the frozen port."""
import threading

import httpx
import pytest

from app.core import ports
from app.core.signing import sign_record
from tests.fixtures.fake_scoring import FakeScoring
from tests.roster.test_roster import scenario, req as roster_req

URL = "/audit/v1/offline-sync"


@pytest.fixture(autouse=True)
def scoring():
    fake = FakeScoring()
    ports.set_scoring(fake)
    yield fake
    ports.set_scoring(None)


def ev(event_id, match_id, typ, payload=None):
    return {"event_id": event_id, "match_id": match_id, "type": typ, "payload": payload or {}}


def act(action_id, body, base=0, ts="2026-10-17T11:00:00Z", typ="score_event"):
    return {"action_id": action_id, "type": typ, "queued_at": ts, "base_version": base, "payload": body}


def sync(client, actions, device="dev-1"):
    r = client.post(URL, json={"device_id": device, "actions": actions})
    assert r.status_code == 200, r.text
    return r.json()


def stub_match(client, mid="m1", device="dev-0"):
    """init + start a match via the coordinator itself, returns the version (2)."""
    out = sync(client, [act("s-init", ev(f"e-{mid}-init", mid, "match_init",
                                       {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2",
                                        "league_id": "league-alpha-1"}), 0, "2026-10-17T09:00:00Z"),
                        act("s-start", ev(f"e-{mid}-start", mid, "match_start"), 1, "2026-10-17T09:00:01Z")],
               device=device)
    assert out["summary"]["applied"] == 2
    return 2


# -------------------------------------------------------------------------- envelope ---------
@pytest.mark.parametrize("body", [
    {}, {"device_id": "d"}, {"device_id": "d", "actions": []}, {"device_id": "d", "actions": "x"},
    {"device_id": "bad id", "actions": [act("a", ev("e", "m", "score"))]},
    {"device_id": "d", "actions": [{"action_id": "a", "type": "other", "queued_at": "2026-10-17T11:00:00Z",
                                    "base_version": 0, "payload": {}}]},
    {"device_id": "d", "actions": [act("a", {}, ts="2026-10-17 11:00:00")]},
    {"device_id": "d", "actions": [act("a", {}, base=True)]},
    {"device_id": "d", "actions": [act("a", {}, base=-1)]},
    {"device_id": "d", "actions": [act("a", "notobject")]},
    {"device_id": "d", "actions": ["notanobject"]},
    {"device_id": "d", "actions": [{"type": "score_event", "queued_at": "2026-10-17T11:00:00Z",
                                    "base_version": 0, "payload": {}}]},
])
def test_envelope_violations_are_400(client, reset, body):
    r = client.post(URL, json=body)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR" and r.json()["error"]["details"]["fields"] != []


def test_exactly_100_actions_accepted_and_101_rejected(client, reset):
    def many(n):
        return [act(f"a{i}", ev(f"ev{i}", "nomatch", "score"), 0, f"2026-10-17T11:{i // 60:02d}:{i % 60:02d}Z")
                for i in range(n)]
    out = sync(client, many(100))
    assert len(out["results"]) == 100 and out["summary"]["rejected"] == 100
    r = client.post(URL, json={"device_id": "dev-1", "actions": many(101)})
    assert r.status_code == 400


# ------------------------------------------------------------------------ happy path ---------
def test_applied_appended_with_signatures_and_versions(client, reset):
    stub = {"sport_id": "football", "home_team_id": "t1", "away_team_id": "t2"}
    score = {"team_id": "t1", "event_type": "goal"}
    out = sync(client, [
        act("a1", ev("evt-1", "m1", "match_init", stub), 0, "2026-10-17T11:00:00Z"),
        act("a2", ev("evt-2", "m1", "match_start"), 1, "2026-10-17T11:00:01Z"),
        act("a3", ev("evt-3", "m1", "score", score), 2, "2026-10-17T11:00:02Z"),
    ])
    assert out["device_id"] == "dev-1"
    assert out["summary"] == {"applied": 3, "rejected": 0, "duplicate": 0}
    for i, r in enumerate(out["results"], start=1):
        assert r["status"] == "applied" and r["resolution"] == "appended" and r["error_code"] is None
        assert r["processed_order"] == i and r["server_version"] == i
    assert out["results"][2]["signature"] == sign_record("evt-3", score, salt="demo-salt")
    assert set(out["results"][0]) == {"action_id", "status", "resolution", "error_code", "processed_order",
                                      "server_version", "signature"}


def test_sorted_by_queued_at_results_in_request_order(client, reset):
    out = sync(client, [
        act("a3", ev("e3", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 2, "2026-10-17T11:00:03Z"),
        act("a1", ev("e1", "m1", "match_init", {"sport_id": "football", "home_team_id": "t1",
                                                  "away_team_id": "t2"}), 0, "2026-10-17T11:00:01Z"),
        act("a2", ev("e2", "m1", "match_start"), 1, "2026-10-17T11:00:02Z"),
    ])
    assert [r["action_id"] for r in out["results"]] == ["a3", "a1", "a2"]          # request order
    assert [r["processed_order"] for r in out["results"]] == [3, 1, 2]             # processing order
    assert out["summary"]["applied"] == 3                                          # sorted run is consistent


def test_tied_timestamps_keep_input_order(client, reset):
    same = "2026-10-17T11:00:00Z"
    out = sync(client, [
        act("b1", ev("e1", "m1", "match_init", {"sport_id": "football", "home_team_id": "t1",
                                                  "away_team_id": "t2"}), 0, same),
        act("b2", ev("e2", "m1", "match_start"), 1, same),
        act("b3", ev("e3", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 2, same),
    ])
    assert [r["processed_order"] for r in out["results"]] == [1, 2, 3]
    assert out["summary"]["applied"] == 3


# ---------------------------------------------------------------------- version rules --------
def test_stale_base_version_is_rebased_append(client, reset):
    stub_match(client)                                         # match at version 2
    out = sync(client, [act("a1", ev("e-s1", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 1)])
    r = out["results"][0]
    assert (r["status"], r["resolution"], r["server_version"]) == ("applied", "rebased_append", 3)
    assert r["signature"]


def test_future_base_version_is_rejected(client, reset):
    stub_match(client)
    out = sync(client, [act("a1", ev("e-f1", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 9)])
    r = out["results"][0]
    assert (r["status"], r["resolution"], r["error_code"]) == ("rejected", "server_wins", "INVALID_BASE_VERSION")
    assert r["server_version"] == 2 and r["signature"] is None
    assert out["summary"] == {"applied": 0, "rejected": 1, "duplicate": 0}


def test_equal_version_after_prior_action_in_same_batch(client, reset):
    stub_match(client)
    out = sync(client, [
        act("a1", ev("e-g1", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 2, "2026-10-17T11:00:00Z"),
        act("a2", ev("e-g2", "m1", "score", {"team_id": "t2", "event_type": "goal"}), 2, "2026-10-17T11:00:01Z"),
    ])
    assert out["results"][0]["resolution"] == "appended"
    assert out["results"][1]["resolution"] == "rebased_append"     # device saw 2, server is at 3 now


# --------------------------------------------------------------------------- rule rejects ----
def test_rule_rejections_are_per_action_and_do_not_block_later_actions(client, reset):
    out = sync(client, [
        act("a1", ev("e1", "m1", "match_init", {"sport_id": "football", "home_team_id": "t1",
                                                  "away_team_id": "t2"}), 0, "2026-10-17T11:00:00Z"),
        act("a2", ev("e2", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 1,
            "2026-10-17T11:00:01Z"),                                   # not started yet
        act("a3", ev("e3", "m1", "match_start"), 1, "2026-10-17T11:00:02Z"),
        act("a4", ev("e4", "m1", "compensation", {"compensates": "ghost", "reason": "x"}), 2,
            "2026-10-17T11:00:03Z"),
        act("a5", ev("e5", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 2, "2026-10-17T11:00:04Z"),
    ])
    st = [(r["status"], r["error_code"]) for r in out["results"]]
    assert st == [("applied", None), ("rejected", "MATCH_NOT_IN_PROGRESS"), ("applied", None),
                  ("rejected", "EVENT_NOT_FOUND"), ("applied", None)]
    assert out["results"][1]["resolution"] == "server_wins" and out["results"][1]["signature"] is None
    assert out["results"][1]["server_version"] == 1                      # unchanged by the rejection
    assert out["summary"] == {"applied": 3, "rejected": 2, "duplicate": 0}


def test_unknown_match_reports_match_not_found(client, reset):
    out = sync(client, [act("a1", ev("e1", "ghost", "score", {"team_id": "t1", "event_type": "goal"}), 0)])
    r = out["results"][0]
    assert (r["status"], r["error_code"], r["server_version"]) == ("rejected", "MATCH_NOT_FOUND", 0)


def test_match_init_for_existing_match_is_match_exists(client, reset):
    stub_match(client)
    out = sync(client, [act("a1", ev("e-again", "m1", "match_init", {"sport_id": "football",
                                                                     "home_team_id": "t1",
                                                                     "away_team_id": "t2"}), 2)])
    assert out["results"][0]["error_code"] == "MATCH_EXISTS"


def test_nested_payload_schema_error_is_per_action_validation_error(client, reset):
    out = sync(client, [act("a1", {"match_id": "m1", "type": "score"}, 0)])
    assert out["results"][0]["error_code"] == "VALIDATION_ERROR" and out["summary"]["rejected"] == 1


# --------------------------------------------------------------------------- duplicates ------
def test_resubmission_makes_every_action_duplicate_and_changes_nothing(client, reset, scoring):
    first = sync(client, [
        act("a1", ev("e1", "m1", "match_init", {"sport_id": "football", "home_team_id": "t1",
                                                  "away_team_id": "t2"}), 0, "2026-10-17T11:00:00Z"),
        act("a2", ev("e2", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 1, "2026-10-17T11:00:01Z"),
    ])
    assert first["summary"] == {"applied": 1, "rejected": 1, "duplicate": 0}       # a2: not started
    batch = [
        act("a1", ev("e1", "m1", "match_init", {"sport_id": "football", "home_team_id": "t1",
                                                  "away_team_id": "t2"}), 0, "2026-10-17T11:00:00Z"),
        act("a2", ev("e2", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 1, "2026-10-17T11:00:01Z"),
    ]
    log_before = list(scoring.matches["m1"]["log"])
    second = sync(client, batch)
    assert second["summary"] == {"applied": 0, "rejected": 0, "duplicate": 2}
    for r in second["results"]:
        assert (r["status"], r["resolution"], r["error_code"], r["signature"]) == \
               ("duplicate", "skipped_duplicate", None, None)
    assert scoring.matches["m1"]["log"] == log_before


def test_same_event_id_identical_payload_from_other_device_is_duplicate(client, reset):
    stub_match(client)
    body = ev("e-dup", "m1", "score", {"team_id": "t1", "event_type": "goal"})
    a = sync(client, [act("x1", body, 2)], device="dev-A")
    b = sync(client, [act("y1", body, 2)], device="dev-B")
    assert a["results"][0]["status"] == "applied"
    r = b["results"][0]
    assert (r["status"], r["resolution"], r["error_code"], r["signature"]) == \
           ("duplicate", "skipped_duplicate", None, None)
    assert r["server_version"] == 3


def test_same_event_id_different_payload_is_duplicate_event_id(client, reset):
    stub_match(client)
    sync(client, [act("x1", ev("e-dup", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 2)])
    out = sync(client, [act("y1", ev("e-dup", "m1", "score", {"team_id": "t2", "event_type": "goal"}), 3)],
               device="dev-B")
    r = out["results"][0]
    assert (r["status"], r["resolution"], r["error_code"]) == ("rejected", "server_wins", "DUPLICATE_EVENT_ID")


def test_duplicate_wins_over_stale_or_future_base_version(client, reset):
    stub_match(client)
    body = ev("e-v", "m1", "score", {"team_id": "t1", "event_type": "goal"})
    sync(client, [act("x1", body, 2)], device="dev-A")
    out = sync(client, [act("y1", body, 99)], device="dev-B")      # future base, but already stored
    assert out["results"][0]["status"] == "duplicate"


def test_same_action_id_twice_in_one_envelope(client, reset):
    stub_match(client)
    body = ev("e-w", "m1", "score", {"team_id": "t1", "event_type": "goal"})
    out = sync(client, [act("same", body, 2, "2026-10-17T11:00:00Z"),
                        act("same", body, 2, "2026-10-17T11:00:05Z")])
    assert [r["status"] for r in out["results"]] == ["applied", "duplicate"]


def test_action_ids_are_scoped_per_device(client, reset):
    stub_match(client)
    a = sync(client, [act("a1", ev("e-1", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 2)], "dev-A")
    b = sync(client, [act("a1", ev("e-2", "m1", "score", {"team_id": "t2", "event_type": "goal"}), 3)], "dev-B")
    assert a["results"][0]["status"] == "applied" and b["results"][0]["status"] == "applied"


def test_reset_clears_dedup_records(client, reset):
    body = [act("a1", ev("e1", "nomatch", "score", {"team_id": "t1", "event_type": "goal"}), 0)]
    assert sync(client, body)["results"][0]["status"] == "rejected"
    assert sync(client, body)["results"][0]["status"] == "duplicate"
    reset()
    assert sync(client, body)["results"][0]["status"] == "rejected"


# ----------------------------------------------------------------------------- roster -------
def setup_roster(client, **kw):
    assert client.post("/audit/v1/roster/setup", json=scenario(**kw)).status_code == 201


def ract(action_id, base=0, ts="2026-10-17T11:01:00Z", **kw):
    return act(action_id, roster_req(**kw), base, ts, "roster_transfer")


def test_roster_actions_versions_and_rejections(client, reset):
    setup_roster(client)
    out = sync(client, [
        ract("r1", 0, "2026-10-17T11:00:00Z", rid="t-1", player="p2", to="sq-b"),
        ract("r2", 0, "2026-10-17T11:00:01Z", rid="t-2", player="p3", to="sq-b"),      # sq-b full now
        ract("r3", 5, "2026-10-17T11:00:02Z", rid="t-3", player="p3", to="sq-c"),      # future base
        ract("r4", 0, "2026-10-17T11:00:03Z", rid="t-4", player="ghost"),
        ract("r5", 0, "2026-10-17T11:00:04Z", rid="t-5", league_id="lg-nope"),
        ract("r6", 0, "2026-10-17T11:00:05Z", rid="t-6", player="p3", to="sq-nope"),
    ])
    rs = {r["action_id"]: r for r in out["results"]}
    assert (rs["r1"]["status"], rs["r1"]["resolution"], rs["r1"]["server_version"]) == ("applied", "appended", 1)
    assert rs["r1"]["signature"] is None
    assert (rs["r2"]["status"], rs["r2"]["error_code"]) == ("rejected", "SQUAD_FULL")
    assert (rs["r3"]["error_code"], rs["r3"]["server_version"]) == ("INVALID_BASE_VERSION", 0)
    assert rs["r4"]["error_code"] == "PLAYER_NOT_FOUND" and rs["r4"]["server_version"] == 0
    assert rs["r5"]["error_code"] == "LEAGUE_NOT_FOUND"
    assert rs["r6"]["error_code"] == "SQUAD_NOT_FOUND"
    assert out["summary"] == {"applied": 1, "rejected": 5, "duplicate": 0}


def test_roster_stale_base_rebases_and_replay_is_duplicate(client, reset):
    setup_roster(client, max_size=10)
    assert client.post("/audit/v1/roster/transfer", json=roster_req(rid="direct", player="p2")).status_code == 201
    out = sync(client, [ract("r1", 0, rid="late", player="p2", frm="sq-b", to="sq-c")])      # device saw 0, now 1
    r = out["results"][0]
    assert (r["status"], r["resolution"], r["server_version"]) == ("applied", "rebased_append", 2)
    # same request_id arriving from another device is a duplicate, not a second move
    again = sync(client, [ract("zz", 0, rid="late", player="p2", frm="sq-b", to="sq-c")], "dev-2")
    assert again["results"][0]["status"] == "duplicate"
    hist = client.get("/audit/v1/roster/history/p2").json()["history"]
    assert len(hist) == 2


def test_roster_request_id_conflict_is_rejected(client, reset):
    setup_roster(client, max_size=10)
    sync(client, [ract("r1", 0, rid="same-id", player="p2")])
    out = sync(client, [ract("r2", 0, rid="same-id", player="p3", to="sq-c")], "dev-2")
    assert out["results"][0]["status"] == "rejected"


def test_mixed_score_and_roster_envelope_is_http_200(client, reset):
    setup_roster(client, max_size=10)
    out = sync(client, [
        act("s1", ev("e1", "ghost", "score", {"team_id": "t1", "event_type": "goal"}), 0, "2026-10-17T11:00:00Z"),
        ract("r1", 0, "2026-10-17T11:00:01Z", rid="m-1", player="p2"),
    ])
    assert [r["status"] for r in out["results"]] == ["rejected", "applied"]


# ----------------------------------------------------------------------------- concurrency ---
def test_concurrent_identical_syncs_apply_each_action_once(client, server, reset, scoring):
    stub_match(client)
    batch = [act("c1", ev("e-c1", "m1", "score", {"team_id": "t1", "event_type": "goal"}), 2, "2026-10-17T11:00:00Z"),
             act("c2", ev("e-c2", "m1", "score", {"team_id": "t2", "event_type": "goal"}), 3, "2026-10-17T11:00:01Z")]
    outs, barrier = [], threading.Barrier(8)

    def worker():
        with httpx.Client(base_url=server, timeout=30) as c:
            barrier.wait()
            outs.append(c.post(URL, json={"device_id": "dev-C", "actions": batch}).json())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sum(o["summary"]["applied"] for o in outs) == 2
    assert sum(o["summary"]["duplicate"] for o in outs) == 14
    assert len(scoring.matches["m1"]["log"]) == 4


def test_concurrent_devices_racing_same_event_id(client, server, reset, scoring):
    stub_match(client)
    body = ev("e-race", "m1", "score", {"team_id": "t1", "event_type": "goal"})
    outs, barrier = [], threading.Barrier(6)

    def worker(i):
        with httpx.Client(base_url=server, timeout=30) as c:
            barrier.wait()
            outs.append(c.post(URL, json={"device_id": f"dev-{i}", "actions": [act("a1", body, 2)]}).json())

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    statuses = sorted(o["results"][0]["status"] for o in outs)
    assert statuses == ["applied"] + ["duplicate"] * 5
    assert len(scoring.matches["m1"]["log"]) == 3
