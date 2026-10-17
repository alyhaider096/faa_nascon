"""Roster, transfer rule order, loans, history, idempotency, concurrency (Section 5.11)."""
import re
import threading

import pytest

TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def scenario(max_size=3, window=("2026-09-01", "2026-09-30"), required=None, live=None):
    league = {"league_id": "lg-r1", "tenant_id": "tenant-alpha", "sport_id": "football",
              "max_squad_size": max_size, "required_positions": {"gk": 1} if required is None else required}
    if window:
        league["transfer_window"] = {"open": window[0], "close": window[1]}
    return {
        "league": league,
        "squads": [
            {"squad_id": "sq-a", "club_id": "club-a", "tenant_id": "tenant-alpha", "name": "A"},
            {"squad_id": "sq-b", "club_id": "club-b", "tenant_id": "tenant-alpha", "name": "B"},
            {"squad_id": "sq-c", "club_id": "club-c", "tenant_id": "tenant-alpha", "name": "C"},
            {"squad_id": "sq-x", "club_id": "club-x", "tenant_id": "tenant-beta", "name": "X"},
        ],
        "players": [
            {"player_id": "p1", "name": "Ali", "position": "gk", "squad_id": "sq-a", "role": "vice_captain"},
            {"player_id": "p2", "name": "Bilal", "position": "df", "squad_id": "sq-a", "role": "captain"},
            {"player_id": "p3", "name": "Cy", "position": "df", "squad_id": "sq-a", "role": "starter"},
            {"player_id": "p4", "name": "Dan", "position": "gk", "squad_id": "sq-b", "role": "starter"},
            {"player_id": "p5", "name": "Eli", "position": "df", "squad_id": "sq-b", "role": "starter"},
            {"player_id": "p6", "name": "Fay", "position": "gk", "squad_id": "sq-x", "role": "starter"},
        ],
        "matches_in_progress": live or [],
    }


def req(rid="tr-001", player="p2", typ="transfer", frm="sq-a", to="sq-b", eff="2026-09-15", end=None, **kw):
    body = {"request_id": rid, "league_id": "lg-r1", "player_id": player, "type": typ, "from_squad_id": frm,
            "to_squad_id": to, "effective_date": eff, "loan_end_date": end, "reason": "Tactical move",
            "requested_by": "user-77"}
    body.update(kw)
    return body


@pytest.fixture()
def setup(client, reset):
    def _setup(**kw):
        r = client.post("/audit/v1/roster/setup", json=scenario(**kw))
        assert r.status_code == 201, r.text
        return r.json()
    return _setup


def post(client, body):
    return client.post("/audit/v1/roster/transfer", json=body)


def code(r):
    return r.json()["error"]["code"]


def hist(client, pid="p2", as_of=None):
    r = client.get(f"/audit/v1/roster/history/{pid}", params={"as_of": as_of} if as_of else None)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------- setup ----------
def test_setup_response_and_replacement(client, setup):
    out = setup()
    assert out == {"league_id": "lg-r1", "status": "configured",
                   "squad_counts": {"sq-a": 3, "sq-b": 2, "sq-c": 0, "sq-x": 1}}
    assert post(client, req()).status_code == 201
    assert len(hist(client)["history"]) == 1
    setup()                                   # re-sending replaces the league's roster state
    assert hist(client)["history"] == []
    assert post(client, req()).status_code == 201   # request_id usable again after replacement


def test_setup_validation_and_references(client, reset):
    bad = scenario()
    del bad["league"]["league_id"]
    r = client.post("/audit/v1/roster/setup", json=bad)
    assert r.status_code == 400 and "league_id" in r.json()["error"]["details"]["fields"]
    r = client.post("/audit/v1/roster/setup", json={**scenario(), "players": "nope"})
    assert r.status_code == 400
    unknown = scenario()
    unknown["league"]["sport_id"] = "no-such-sport"
    r = client.post("/audit/v1/roster/setup", json=unknown)
    assert r.status_code == 404 and code(r) == "SPORT_NOT_FOUND"
    badsq = scenario()
    badsq["players"][0]["squad_id"] = "sq-nope"
    r = client.post("/audit/v1/roster/setup", json=badsq)
    assert r.status_code == 404 and code(r) == "SQUAD_NOT_FOUND"
    badrole = scenario()
    badrole["players"][0]["role"] = "boss"
    assert client.post("/audit/v1/roster/setup", json=badrole).status_code == 400
    badwin = scenario(window=("2026-09-30", "2026-09-01"))
    assert client.post("/audit/v1/roster/setup", json=badwin).status_code == 400


def test_defaults_come_from_sport_roster_config(client, reset):
    s = scenario()
    del s["league"]["max_squad_size"]
    del s["league"]["required_positions"]
    assert client.post("/audit/v1/roster/setup", json=s).status_code == 201
    # football config: gk >= 1 -> p1 is sq-a's only goalkeeper
    r = post(client, req(player="p1", to="sq-c"))
    assert r.status_code == 409 and code(r) == "MIN_POSITION_VIOLATION"
    assert post(client, req(player="p2", to="sq-c")).status_code == 201   # max defaults to 25, not 3


# ------------------------------------------------------------------------ happy paths -------
def test_transfer_response_shape_and_effects(client, setup):
    setup()
    r = post(client, req())
    assert r.status_code == 201
    b = r.json()
    assert b["request_id"] == "tr-001" and b["status"] == "accepted"
    assert b["state"] == "active" and b["blocking_match_id"] is None
    assert b["registration"] == {"player_id": "p2", "league_id": "lg-r1", "squad_id": "sq-b",
                                 "parent_squad_id": None, "registration_type": "transfer",
                                 "start_date": "2026-09-15", "loan_end_date": None, "role": "substitute"}
    a = b["audit_entry"]
    assert a["audit_id"] == "au-0001" and a["action"] == "transfer" and a["player_id"] == "p2"
    assert a["from_squad_id"] == "sq-a" and a["to_squad_id"] == "sq-b" and a["effective_date"] == "2026-09-15"
    assert a["state"] == "active" and a["who"] == "user-77" and a["why"] == "Tactical move"
    assert TS.match(a["when"])
    h = hist(client)
    assert h["current_squad_id"] == "sq-b" and h["parent_squad_id"] is None and h["league_id"] == "lg-r1"
    assert h["history"] == [a]


def test_replay_returns_200_same_body_and_changed_body_conflicts(client, setup):
    setup()
    first = post(client, req())
    again = post(client, req())
    assert again.status_code == 200 and again.json() == first.json()
    assert len(hist(client)["history"]) == 1
    changed = post(client, req(to="sq-c"))
    assert changed.status_code == 409 and code(changed) == "DUPLICATE_REQUEST_ID"


def test_replay_is_judged_before_current_state(client, setup):
    setup()
    assert post(client, req()).status_code == 201           # p2 leaves sq-a
    # re-sending would now fail NOT_IN_SQUAD as a new request, but it is an identical replay
    assert post(client, req()).status_code == 200


def test_release_any_date_and_ignores_destination(client, setup):
    setup()
    r = post(client, req(typ="release", to=None, eff="2027-03-03"))
    assert r.status_code == 201
    b = r.json()
    assert b["registration"] is None and b["audit_entry"]["action"] == "release"
    assert b["audit_entry"]["to_squad_id"] is None
    h = hist(client, as_of="2027-03-04")
    assert h["current_squad_id"] is None
    r2 = post(client, req(rid="tr-002", player="p3", typ="release", to="sq-b", eff="2026-01-01"))
    assert r2.status_code == 201 and r2.json()["registration"] is None


# -------------------------------------------------------------------------- validation (1) ---
@pytest.mark.parametrize("mutate,field", [
    (lambda b: b.update(type="sell"), "type"),
    (lambda b: b.update(effective_date="2026-9-15"), "effective_date"),
    (lambda b: b.update(effective_date="2026-02-30"), "effective_date"),
    (lambda b: b.pop("effective_date"), "effective_date"),
    (lambda b: b.update(to_squad_id=None), "to_squad_id"),
    (lambda b: b.pop("from_squad_id"), "from_squad_id"),
    (lambda b: b.update(request_id="has space"), "request_id"),
    (lambda b: b.update(player_id=5), "player_id"),
    (lambda b: b.update(typ="loan") or b.update(type="loan", loan_end_date=None), "loan_end_date"),
    (lambda b: b.update(type="loan", loan_end_date="2026-09-15"), "loan_end_date"),
    (lambda b: b.update(type="loan", loan_end_date="2026-09-14"), "loan_end_date"),
    (lambda b: b.update(type="loan", loan_end_date="soon"), "loan_end_date"),
    (lambda b: b.update(requested_by=7), "requested_by"),
])
def test_validation_is_400_with_fields(client, setup, mutate, field):
    setup()
    body = req()
    mutate(body)
    r = post(client, body)
    assert r.status_code == 400, r.text
    assert code(r) == "VALIDATION_ERROR" and field in r.json()["error"]["details"]["fields"]


def test_unknown_fields_are_ignored(client, setup):
    setup()
    assert post(client, req(surprise="x")).status_code == 201


# ------------------------------------------------------------------ the eight checks ---------
def test_check2_existence_codes_and_order(client, setup):
    setup()
    r = post(client, req(league_id="lg-nope"))
    assert (r.status_code, code(r)) == (404, "LEAGUE_NOT_FOUND")
    r = post(client, req(player="p-nope"))
    assert (r.status_code, code(r)) == (404, "PLAYER_NOT_FOUND")
    r = post(client, req(frm="sq-nope"))
    assert (r.status_code, code(r)) == (404, "SQUAD_NOT_FOUND")
    r = post(client, req(to="sq-nope"))
    assert (r.status_code, code(r)) == (404, "SQUAD_NOT_FOUND")
    # combined: league beats player beats squad
    r = post(client, req(league_id="lg-nope", player="p-nope", frm="sq-nope"))
    assert code(r) == "LEAGUE_NOT_FOUND"
    r = post(client, req(player="p-nope", frm="sq-nope"))
    assert code(r) == "PLAYER_NOT_FOUND"
    # a 400 beats any 404
    r = post(client, req(league_id="lg-nope", type="sell"))
    assert code(r) == "VALIDATION_ERROR"


def test_check3_cross_tenant(client, setup):
    setup()
    r = post(client, req(to="sq-x"))
    assert (r.status_code, code(r)) == (409, "CROSS_TENANT_TRANSFER")
    # beats NOT_IN_SQUAD and a closed window
    r = post(client, req(frm="sq-b", to="sq-x", eff="2026-10-05"))
    assert code(r) == "CROSS_TENANT_TRANSFER"


def test_check4_not_in_squad_beats_window(client, setup):
    setup()
    r = post(client, req(frm="sq-b"))
    assert (r.status_code, code(r)) == (409, "NOT_IN_SQUAD")
    r = post(client, req(frm="sq-b", eff="2026-10-05"))
    assert code(r) == "NOT_IN_SQUAD"


def test_check5_window_inclusive_and_release_exempt(client, setup):
    setup(max_size=10)
    for i, (day, ok) in enumerate([("2026-08-31", False), ("2026-09-01", True), ("2026-09-30", True),
                                   ("2026-10-01", False)]):
        player = ["p2", "p3", "p5", "p2"][i]
        frm = "sq-a" if player in ("p2", "p3") else "sq-b"
        to = "sq-b" if frm == "sq-a" else "sq-c"
        r = post(client, req(rid=f"w{i}", player=player, frm=frm, to=to, eff=day))
        if ok:
            assert r.status_code == 201, (day, r.text)
        else:
            assert (r.status_code, code(r)) == (409, "TRANSFER_WINDOW_CLOSED"), day
    assert post(client, req(rid="rel", player="p3", typ="release", to=None, frm="sq-b",
                            eff="2026-12-25")).status_code == 201


def test_check6_on_loan_blocks_everything_and_beats_capacity(client, setup):
    setup()
    loan = post(client, req(rid="ln", typ="loan", eff="2026-09-10", end="2026-09-20"))
    assert loan.status_code == 201
    for typ, to in (("transfer", "sq-c"), ("loan", "sq-c"), ("release", None)):
        r = post(client, req(rid=f"x-{typ}", typ=typ, frm="sq-b", to=to, eff="2026-09-12",
                             end="2026-09-18" if typ == "loan" else None))
        assert (r.status_code, code(r)) == (409, "PLAYER_ON_LOAN"), typ
    # on loan AND destination full -> ON_LOAN wins (check 6 before 7)
    r = post(client, req(rid="x-full", frm="sq-b", to="sq-a", eff="2026-09-12"))
    assert code(r) == "PLAYER_ON_LOAN"
    # window closed AND on loan -> window wins (check 5 before 6)
    r = post(client, req(rid="x-win", frm="sq-b", to="sq-c", eff="2026-10-05"))
    assert code(r) == "TRANSFER_WINDOW_CLOSED"


def test_check7_squad_full_and_beats_min_position(client, setup):
    setup()
    r = post(client, req(player="p5", frm="sq-b", to="sq-a"))          # sq-a already has 3
    assert (r.status_code, code(r)) == (409, "SQUAD_FULL")
    # p4 is sq-b's only gk (check 8 would fail too) but SQUAD_FULL is evaluated first
    r = post(client, req(rid="tr-9", player="p4", frm="sq-b", to="sq-a"))
    assert code(r) == "SQUAD_FULL"
    # release has no capacity check: p3 can leave a full squad
    assert post(client, req(rid="tr-8", player="p3", typ="release", to=None)).status_code == 201


def test_check8_min_position_for_transfer_loan_and_release(client, setup):
    setup()
    for typ in ("transfer", "loan", "release"):
        r = post(client, req(rid=f"mp-{typ}", player="p4", typ=typ, frm="sq-b",
                             to=None if typ == "release" else "sq-c", eff="2026-09-12",
                             end="2026-09-20" if typ == "loan" else None))
        assert (r.status_code, code(r)) == (409, "MIN_POSITION_VIOLATION"), typ


def test_rejection_leaves_no_writes(client, setup):
    setup()
    for body in (req(to="sq-x"), req(frm="sq-b"), req(eff="2026-10-05"), req(player="p4", frm="sq-b", to="sq-c")):
        assert post(client, body).status_code in (409,)
    assert hist(client)["history"] == [] and hist(client, "p4")["history"] == []
    assert hist(client)["current_squad_id"] == "sq-a"
    # the same request_id still works afterwards because rejections are not recorded
    assert post(client, req()).status_code == 201


# ---------------------------------------------------------------------------- roles ---------
def test_move_makes_substitute_and_vacates_captaincy(client, setup):
    setup()
    r = post(client, req(player="p2"))                 # p2 was captain
    assert r.json()["registration"]["role"] == "substitute"
    r = post(client, req(rid="tr-vc", player="p3", to="sq-c"))
    assert r.json()["registration"]["role"] == "substitute"


# ----------------------------------------------------------------------------- loans --------
def test_loan_counts_at_borrower_only(client, setup):
    setup()
    r = post(client, req(rid="ln", typ="loan", eff="2026-09-10", end="2026-09-20"))
    b = r.json()
    assert b["registration"] == {"player_id": "p2", "league_id": "lg-r1", "squad_id": "sq-b",
                                 "parent_squad_id": "sq-a", "registration_type": "loan",
                                 "start_date": "2026-09-10", "loan_end_date": "2026-09-20", "role": "substitute"}
    assert b["audit_entry"]["action"] == "loan"
    # borrower sq-b now holds 3 (p4, p5, p2) -> full
    assert code(post(client, req(rid="t1", player="p6", frm="sq-x", to="sq-b"))) == "CROSS_TENANT_TRANSFER"
    assert code(post(client, req(rid="t2", player="p3", to="sq-b"))) == "SQUAD_FULL"
    # lender sq-a dropped to 2 -> a slot is free again
    assert post(client, req(rid="t3", player="p5", frm="sq-b", to="sq-a")).status_code == 201


def test_loan_return_inclusive_end_and_idempotent(client, setup):
    setup()
    post(client, req(rid="ln", typ="loan", eff="2026-09-10", end="2026-09-20"))
    h = hist(client, as_of="2026-09-20")                      # last loan day: still on loan
    assert h["current_squad_id"] == "sq-b" and h["parent_squad_id"] == "sq-a"
    assert [e["action"] for e in h["history"]] == ["loan"]
    h = hist(client, as_of="2026-09-21")                      # the day after: returned
    assert h["current_squad_id"] == "sq-a" and h["parent_squad_id"] is None
    assert [e["action"] for e in h["history"]] == ["loan", "loan_return"]
    ret = h["history"][1]
    assert ret["who"] == "system" and ret["from_squad_id"] == "sq-b" and ret["to_squad_id"] == "sq-a"
    assert ret["effective_date"] == "2026-09-21" and ret["state"] == "active"
    for _ in range(3):                                         # repeated reads never duplicate it
        assert len(hist(client, as_of="2027-01-05")["history"]) == 2
    # reads reflect the effective date even after the return was recorded
    assert hist(client, as_of="2026-09-15")["current_squad_id"] == "sq-b"
    # after return the player is no longer "on loan"
    assert post(client, req(rid="back", player="p2", to="sq-c", eff="2026-09-25")).status_code == 201


def test_history_default_as_of_is_today_and_triggers_return(client, setup):
    setup()
    post(client, req(rid="ln", typ="loan", eff="2026-09-10", end="2026-09-20"))
    h = client.get("/audit/v1/roster/history/p2").json()
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", h["as_of"])
    assert [e["action"] for e in h["history"]][-1] == "loan_return"


def test_history_errors(client, setup):
    setup()
    r = client.get("/audit/v1/roster/history/p-nope")
    assert (r.status_code, code(r)) == (404, "PLAYER_NOT_FOUND")
    r = client.get("/audit/v1/roster/history/p2", params={"as_of": "01-02-2026"})
    assert (r.status_code, code(r)) == (400, "VALIDATION_ERROR")


def test_audit_ids_increment(client, setup):
    setup(max_size=10)
    a = post(client, req(rid="a", player="p2")).json()["audit_entry"]["audit_id"]
    b = post(client, req(rid="b", player="p3")).json()["audit_entry"]["audit_id"]
    assert (a, b) == ("au-0001", "au-0002")


# -------------------------------------------------------------------- deferred (edge 6) ------
def test_last_day_move_with_live_match_is_deferred(client, setup):
    setup(live=[{"match_id": "m-live", "home_squad_id": "sq-a", "away_squad_id": "sq-b"}])
    r = post(client, req(eff="2026-09-30"))                      # last inclusive window day
    assert r.status_code == 201
    b = r.json()
    assert b["state"] == "deferred_until_match_end" and b["blocking_match_id"] == "m-live"
    assert b["audit_entry"]["state"] == "deferred_until_match_end"
    assert b["registration"]["squad_id"] == "sq-b"


def test_player_outside_live_match_is_active(client, setup):
    setup(live=[{"match_id": "m-live", "home_squad_id": "sq-a", "away_squad_id": "sq-x"}])
    r = post(client, req(rid="t", player="p5", frm="sq-b", to="sq-c", eff="2026-09-30"))
    assert r.json()["state"] == "active" and r.json()["blocking_match_id"] is None


# ----------------------------------------------------------------------- concurrency ---------
def test_concurrent_transfers_respect_capacity(client, server, reset):
    import httpx
    s = scenario(max_size=2, required={})
    s["players"] = [{"player_id": f"q{i}", "position": "df", "squad_id": "sq-a", "role": "starter"}
                    for i in range(8)]
    assert client.post("/audit/v1/roster/setup", json=s).status_code == 201
    results, barrier = [], threading.Barrier(8)

    def worker(i):
        with httpx.Client(base_url=server, timeout=30) as c:
            barrier.wait()
            results.append(c.post("/audit/v1/roster/transfer",
                                  json=req(rid=f"cc-{i}", player=f"q{i}", to="sq-c")).status_code)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [201, 201] + [409] * 6


def test_concurrent_identical_request_ids_apply_once(client, server, setup):
    import httpx
    setup()
    results, barrier = [], threading.Barrier(6)

    def worker():
        with httpx.Client(base_url=server, timeout=30) as c:
            barrier.wait()
            results.append(c.post("/audit/v1/roster/transfer", json=req(rid="same")).status_code)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [200] * 5 + [201]
    assert len(hist(client)["history"]) == 1
