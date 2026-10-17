"""Roster, transfers, loans and audit history (Section 5.11).

All functions take the caller's open connection and never commit; the caller owns the
transaction (API route = one transaction, offline coordinator = one savepoint per action).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..core.errors import DomainError, validation_error
from ..core.signing import request_hash
from ..core.validation import Fields, is_int, is_id, parse_date, utc_now_str

ROLE_VALUES = ("captain", "vice_captain", "starter", "substitute")
MOVE_TYPES = ("transfer", "loan", "release")


# --------------------------------------------------------------------------- setup ----------
def _both(f: Fields, path: str, leaf: str) -> None:
    f.add(path)
    f.add(leaf)


def _validate_setup(body: dict) -> dict:
    f = Fields()
    league = body.get("league")
    squads = body.get("squads")
    players = body.get("players")
    matches = body.get("matches_in_progress", [])
    out: dict[str, Any] = {}

    if not isinstance(league, dict):
        f.add("league")
        league = {}
    if not isinstance(squads, list):
        f.add("squads")
        squads = []
    if not isinstance(players, list):
        f.add("players")
        players = []
    if matches is None:
        matches = []
    if not isinstance(matches, list):
        f.add("matches_in_progress")
        matches = []

    lg: dict[str, Any] = {}
    for key in ("league_id", "tenant_id", "sport_id"):
        if not is_id(league.get(key)):
            _both(f, "league." + key, key)
        else:
            lg[key] = league[key]
    window = league.get("transfer_window")
    lg["window_open"] = lg["window_close"] = None
    if window is not None:
        if not isinstance(window, dict):
            _both(f, "league.transfer_window", "transfer_window")
        else:
            o, c = parse_date(window.get("open")), parse_date(window.get("close"))
            if o is None:
                _both(f, "league.transfer_window.open", "open")
            if c is None:
                _both(f, "league.transfer_window.close", "close")
            if o is not None and c is not None:
                if o > c:
                    _both(f, "league.transfer_window", "transfer_window")
                else:
                    lg["window_open"], lg["window_close"] = o, c
    msz = league.get("max_squad_size")
    if msz is not None and (not is_int(msz) or msz < 1):
        _both(f, "league.max_squad_size", "max_squad_size")
        msz = None
    lg["max_squad_size"] = msz
    req = league.get("required_positions")
    if req is not None:
        if not isinstance(req, dict) or any(
            (not isinstance(k, str) or not k or not is_int(v) or v < 0) for k, v in req.items()
        ):
            _both(f, "league.required_positions", "required_positions")
            req = None
    lg["required_positions"] = req
    out["league"] = lg

    sq_list = []
    for i, s in enumerate(squads):
        if not isinstance(s, dict):
            f.add(f"squads[{i}]")
            continue
        row = {}
        for key in ("squad_id", "club_id", "tenant_id"):
            if not is_id(s.get(key)):
                _both(f, f"squads[{i}].{key}", key)
            else:
                row[key] = s[key]
        name = s.get("name", "")
        if not isinstance(name, str) or len(name) > 200:
            _both(f, f"squads[{i}].name", "name")
            name = ""
        row["name"] = name
        sq_list.append(row)
    out["squads"] = sq_list

    pl_list = []
    for i, p in enumerate(players):
        if not isinstance(p, dict):
            f.add(f"players[{i}]")
            continue
        row = {}
        if not is_id(p.get("player_id")):
            _both(f, f"players[{i}].player_id", "player_id")
        else:
            row["player_id"] = p["player_id"]
        pos = p.get("position")
        if not isinstance(pos, str) or not (1 <= len(pos) <= 40):
            _both(f, f"players[{i}].position", "position")
        else:
            row["position"] = pos
        sid = p.get("squad_id")
        if sid is not None and not is_id(sid):
            _both(f, f"players[{i}].squad_id", "squad_id")
        row["squad_id"] = sid
        role = p.get("role", "substitute")
        if role not in ROLE_VALUES:
            _both(f, f"players[{i}].role", "role")
        row["role"] = role
        name = p.get("name", "")
        if not isinstance(name, str) or len(name) > 200:
            _both(f, f"players[{i}].name", "name")
            name = ""
        row["name"] = name
        pl_list.append(row)
    out["players"] = pl_list

    m_list = []
    for i, m in enumerate(matches):
        if not isinstance(m, dict):
            f.add(f"matches_in_progress[{i}]")
            continue
        row = {}
        for key in ("match_id", "home_squad_id", "away_squad_id"):
            if not is_id(m.get(key)):
                _both(f, f"matches_in_progress[{i}].{key}", key)
            else:
                row[key] = m[key]
        m_list.append(row)
    out["matches"] = m_list
    f.check()
    return out


def setup(conn, body: dict) -> dict:
    v = _validate_setup(body)
    lg = v["league"]
    league_id = lg["league_id"]

    sport = conn.execute("SELECT config FROM sports WHERE sport_id=%s", (lg["sport_id"],)).fetchone()
    if sport is None:
        raise DomainError(404, "SPORT_NOT_FOUND", f"Sport {lg['sport_id']} does not exist.",
                          {"sport_id": lg["sport_id"]})
    roster_cfg = (sport["config"] or {}).get("roster", {}) or {}
    max_size = lg["max_squad_size"] if lg["max_squad_size"] is not None else roster_cfg.get("max_squad_size")
    if not is_int(max_size) or max_size < 1:
        raise validation_error(["max_squad_size"], "max_squad_size is required for this sport.")
    required = lg["required_positions"]
    if required is None:
        required = roster_cfg.get("required_positions", {}) or {}

    squad_ids = {s["squad_id"] for s in v["squads"]}
    for p in v["players"]:
        if p["squad_id"] is not None and p["squad_id"] not in squad_ids:
            raise DomainError(404, "SQUAD_NOT_FOUND", f"Squad {p['squad_id']} does not exist.",
                              {"squad_id": p["squad_id"]})

    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("rl:" + league_id,))
    # Replace this league's roster state wholesale (also frees ids re-used from another league).
    pids = [p["player_id"] for p in v["players"]]
    conn.execute("DELETE FROM roster_audit WHERE league_id=%s OR player_id = ANY(%s)", (league_id, pids))
    conn.execute("DELETE FROM roster_requests WHERE league_id=%s", (league_id,))
    conn.execute("DELETE FROM roster_matches WHERE league_id=%s", (league_id,))
    conn.execute("DELETE FROM roster_players WHERE league_id=%s OR player_id = ANY(%s)", (league_id, pids))
    conn.execute("DELETE FROM roster_squads WHERE league_id=%s OR squad_id = ANY(%s)",
                 (league_id, list(squad_ids)))
    conn.execute("DELETE FROM roster_leagues WHERE league_id=%s", (league_id,))

    conn.execute(
        "INSERT INTO roster_leagues (league_id, tenant_id, sport_id, window_open, window_close,"
        " max_squad_size, required_positions) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (league_id, lg["tenant_id"], lg["sport_id"], lg["window_open"], lg["window_close"],
         max_size, _json(required)),
    )
    for s in v["squads"]:
        conn.execute(
            "INSERT INTO roster_squads (squad_id, league_id, club_id, tenant_id, name)"
            " VALUES (%s,%s,%s,%s,%s)",
            (s["squad_id"], league_id, s["club_id"], s["tenant_id"], s["name"]),
        )
    for p in v["players"]:
        reg_type = "registered" if p["squad_id"] else None
        conn.execute(
            "INSERT INTO roster_players (player_id, league_id, name, position, initial_squad_id,"
            " initial_role, squad_id, registration_type, role)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (p["player_id"], league_id, p["name"], p["position"], p["squad_id"], p["role"],
             p["squad_id"], reg_type, p["role"] if p["squad_id"] else None),
        )
    for i, m in enumerate(v["matches"]):
        conn.execute(
            "INSERT INTO roster_matches (match_id, league_id, home_squad_id, away_squad_id, position)"
            " VALUES (%s,%s,%s,%s,%s) ON CONFLICT (match_id) DO UPDATE SET league_id=EXCLUDED.league_id,"
            " home_squad_id=EXCLUDED.home_squad_id, away_squad_id=EXCLUDED.away_squad_id,"
            " position=EXCLUDED.position",
            (m["match_id"], league_id, m["home_squad_id"], m["away_squad_id"], i),
        )
    counts = {s["squad_id"]: 0 for s in v["squads"]}
    for p in v["players"]:
        if p["squad_id"] is not None:
            counts[p["squad_id"]] += 1
    return {"league_id": league_id, "status": "configured", "squad_counts": counts}


def _json(value: Any):
    from psycopg.types.json import Jsonb
    return Jsonb(value)


# ------------------------------------------------------------------------- transfer ---------
def _validate_transfer(body: dict) -> dict:
    f = Fields()
    out: dict[str, Any] = {}
    out["request_id"] = f.need_id(body, "request_id")
    out["league_id"] = f.need_id(body, "league_id")
    out["player_id"] = f.need_id(body, "player_id")
    typ = body.get("type")
    if typ not in MOVE_TYPES:
        f.add("type")
    out["type"] = typ
    out["from_squad_id"] = f.need_id(body, "from_squad_id")
    to = body.get("to_squad_id")
    if typ == "release":
        if to is not None and not is_id(to):
            f.add("to_squad_id")
        to = None
    elif not is_id(to):
        f.add("to_squad_id")
        to = None
    out["to_squad_id"] = to
    eff = f.need_date(body, "effective_date")
    out["effective_date"] = eff
    end = None
    if typ == "loan":
        end = parse_date(body.get("loan_end_date"))
        if end is None or (eff is not None and end <= eff):
            f.add("loan_end_date")
    elif body.get("loan_end_date") is not None and parse_date(body.get("loan_end_date")) is None:
        f.add("loan_end_date")
    out["loan_end_date"] = end
    reason = body.get("reason", "")
    if not isinstance(reason, str) or len(reason) > 500:
        f.add("reason")
        reason = ""
    who = body.get("requested_by", "unknown")
    if not isinstance(who, str) or not (1 <= len(who) <= 200):
        f.add("requested_by")
        who = "unknown"
    out["reason"], out["requested_by"] = reason, who
    f.check()
    out["_hash"] = request_hash({
        "request_id": body["request_id"], "league_id": body["league_id"],
        "player_id": body["player_id"], "type": typ, "from_squad_id": body["from_squad_id"],
        "to_squad_id": body.get("to_squad_id"), "effective_date": body["effective_date"],
        "loan_end_date": body.get("loan_end_date"), "reason": reason, "requested_by": who,
    })
    return out


def _next_audit(conn) -> tuple[int, str]:
    seq = conn.execute("SELECT nextval('roster_audit_seq') AS n").fetchone()["n"]
    return seq, f"au-{seq:04d}"


def _audit_json(row: dict) -> dict:
    return {
        "audit_id": row["audit_id"], "action": row["action"], "player_id": row["player_id"],
        "league_id": row["league_id"], "from_squad_id": row["from_squad_id"],
        "to_squad_id": row["to_squad_id"], "effective_date": row["effective_date"].isoformat(),
        "state": row["state"], "who": row["who"], "when": row["when"], "why": row["why"],
    }


def _registration_json(p: dict) -> dict | None:
    if p["squad_id"] is None:
        return None
    return {
        "player_id": p["player_id"], "league_id": p["league_id"], "squad_id": p["squad_id"],
        "parent_squad_id": p["parent_squad_id"], "registration_type": p["registration_type"],
        "start_date": p["start_date"].isoformat() if p["start_date"] else None,
        "loan_end_date": p["loan_end_date"].isoformat() if p["loan_end_date"] else None,
        "role": p["role"],
    }


def _load_refs(conn, v: dict, *, lock: bool):
    """Check 2 of Section 5.11: league, player, then squads must exist (404s, in that order)."""
    suffix = " FOR UPDATE" if lock else ""
    league_id = v["league_id"]
    league = conn.execute("SELECT * FROM roster_leagues WHERE league_id=%s", (league_id,)).fetchone()
    if league is None:
        raise DomainError(404, "LEAGUE_NOT_FOUND", f"League {league_id} does not exist.",
                          {"league_id": league_id})
    player = conn.execute("SELECT * FROM roster_players WHERE player_id=%s" + suffix,
                          (v["player_id"],)).fetchone()
    if player is None or player["league_id"] != league_id:
        raise DomainError(404, "PLAYER_NOT_FOUND", f"Player {v['player_id']} does not exist.",
                          {"player_id": v["player_id"]})
    squads: dict[str, dict] = {}
    for key in ("from_squad_id", "to_squad_id"):
        sid = v[key]
        if sid is None:
            continue
        row = conn.execute("SELECT * FROM roster_squads WHERE squad_id=%s AND league_id=%s" + suffix,
                           (sid, league_id)).fetchone()
        if row is None:
            raise DomainError(404, "SQUAD_NOT_FOUND", f"Squad {sid} does not exist.", {"squad_id": sid})
        squads[sid] = row
    return league, player, squads[v["from_squad_id"]], (squads[v["to_squad_id"]] if v["to_squad_id"] else None)


def validate_transfer(body: dict) -> dict:
    """Public: schema check (step 1) so other services can inspect a request before applying it."""
    return _validate_transfer(body)


def check_references(conn, v: dict) -> None:
    """Public: existence checks only (404s), without locking or writing."""
    _load_refs(conn, v, lock=False)


def find_request(conn, request_id: str):
    return conn.execute("SELECT body_hash, response FROM roster_requests WHERE request_id=%s",
                        (request_id,)).fetchone()


def transfer(conn, body: dict) -> tuple[int, dict]:
    """Apply a transfer/loan/release. Returns (201, body) or (200, stored body) on replay.

    Rule checks run in the exact order of Section 5.11 and a rejection writes nothing.
    """
    v = _validate_transfer(body)                                                   # 1 schema
    request_id, league_id = v["request_id"], v["league_id"]

    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("rreq:" + request_id,))
    prior = conn.execute("SELECT body_hash, response FROM roster_requests WHERE request_id=%s",
                         (request_id,)).fetchone()
    if prior is not None:                                  # replay is judged before current state
        if prior["body_hash"] == v["_hash"]:
            return 200, prior["response"]
        raise DomainError(409, "DUPLICATE_REQUEST_ID",
                          f"request_id {request_id} was already used with a different body.",
                          {"request_id": request_id})

    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("rl:" + league_id,))
    league, player, from_sq, to_sq = _load_refs(conn, v, lock=True)                # 2 existence

    for sq in (from_sq, to_sq):                                                    # 3 tenant
        if sq is not None and sq["tenant_id"] != league["tenant_id"]:
            raise DomainError(409, "CROSS_TENANT_TRANSFER",
                              "Squads must belong to the league's tenant.",
                              {"squad_id": sq["squad_id"], "tenant_id": league["tenant_id"]})

    if player["squad_id"] != v["from_squad_id"]:                                   # 4 membership
        raise DomainError(409, "NOT_IN_SQUAD",
                          f"Player {player['player_id']} is not in squad {v['from_squad_id']}.",
                          {"player_id": player["player_id"], "squad_id": v["from_squad_id"]})

    eff: date = v["effective_date"]
    if v["type"] != "release" and league["window_open"] is not None:               # 5 window
        if not (league["window_open"] <= eff <= league["window_close"]):
            raise DomainError(409, "TRANSFER_WINDOW_CLOSED",
                              "The transfer window is closed for this date.",
                              {"effective_date": eff.isoformat(),
                               "open": league["window_open"].isoformat(),
                               "close": league["window_close"].isoformat()})

    if player["registration_type"] == "loan":                                      # 6 on loan
        raise DomainError(409, "PLAYER_ON_LOAN", f"Player {player['player_id']} is currently on loan.",
                          {"player_id": player["player_id"]})

    if v["type"] != "release":                                                     # 7 capacity
        n = conn.execute("SELECT count(*) AS n FROM roster_players WHERE squad_id=%s",
                         (v["to_squad_id"],)).fetchone()["n"]
        if n + 1 > league["max_squad_size"]:
            raise DomainError(409, "SQUAD_FULL", f"Squad {v['to_squad_id']} is full.",
                              {"squad_id": v["to_squad_id"], "max_squad_size": league["max_squad_size"]})

    need = (league["required_positions"] or {}).get(player["position"], 0)         # 8 minimum
    have = conn.execute("SELECT count(*) AS n FROM roster_players WHERE squad_id=%s AND position=%s",
                        (v["from_squad_id"], player["position"])).fetchone()["n"]
    if have - 1 < need:
        raise DomainError(409, "MIN_POSITION_VIOLATION",
                          f"Squad {v['from_squad_id']} must keep {need} {player['position']}.",
                          {"squad_id": v["from_squad_id"], "position": player["position"],
                           "required": need})

    # ---- accepted: effects ---------------------------------------------------------------
    live = conn.execute(
        "SELECT match_id FROM roster_matches WHERE league_id=%s AND (home_squad_id=%s OR away_squad_id=%s)"
        " ORDER BY position LIMIT 1", (league_id, v["from_squad_id"], v["from_squad_id"]),
    ).fetchone()
    state = "deferred_until_match_end" if live else "active"
    blocking = live["match_id"] if live else None

    if v["type"] == "release":
        conn.execute(
            "UPDATE roster_players SET squad_id=NULL, parent_squad_id=NULL, registration_type=NULL,"
            " start_date=NULL, loan_end_date=NULL, role=NULL WHERE player_id=%s", (player["player_id"],))
    elif v["type"] == "transfer":
        conn.execute(
            "UPDATE roster_players SET squad_id=%s, parent_squad_id=NULL, registration_type='transfer',"
            " start_date=%s, loan_end_date=NULL, role='substitute' WHERE player_id=%s",
            (v["to_squad_id"], eff, player["player_id"]))
    else:
        conn.execute(
            "UPDATE roster_players SET squad_id=%s, parent_squad_id=%s, registration_type='loan',"
            " start_date=%s, loan_end_date=%s, role='substitute' WHERE player_id=%s",
            (v["to_squad_id"], v["from_squad_id"], eff, v["loan_end_date"], player["player_id"]))

    seq, audit_id = _next_audit(conn)
    conn.execute(
        "INSERT INTO roster_audit (seq, audit_id, player_id, league_id, action, from_squad_id,"
        " to_squad_id, effective_date, state, who, \"when\", why)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (seq, audit_id, player["player_id"], league_id, v["type"], v["from_squad_id"],
         v["to_squad_id"], eff, state, v["requested_by"], utc_now_str(), v["reason"]))
    audit = conn.execute("SELECT * FROM roster_audit WHERE seq=%s", (seq,)).fetchone()
    updated = conn.execute("SELECT * FROM roster_players WHERE player_id=%s", (player["player_id"],)).fetchone()

    response = {
        "request_id": request_id, "status": "accepted", "state": state, "blocking_match_id": blocking,
        "registration": _registration_json(updated), "audit_entry": _audit_json(audit),
    }
    conn.execute("INSERT INTO roster_requests (request_id, league_id, body_hash, response)"
                 " VALUES (%s,%s,%s,%s)", (request_id, league_id, v["_hash"], _json(response)))
    return 201, response


# -------------------------------------------------------------------------- history ----------
def player_version(conn, player_id: str) -> int | None:
    """Roster version = number of audit entries for the player; None if the player is unknown."""
    if conn.execute("SELECT 1 FROM roster_players WHERE player_id=%s", (player_id,)).fetchone() is None:
        return None
    return conn.execute("SELECT count(*) AS n FROM roster_audit WHERE player_id=%s",
                        (player_id,)).fetchone()["n"]


def _apply_loan_return(conn, player: dict) -> None:
    ret_date = player["loan_end_date"] + timedelta(days=1)
    borrower, lender = player["squad_id"], player["parent_squad_id"]
    conn.execute(
        "UPDATE roster_players SET squad_id=%s, parent_squad_id=NULL, registration_type='registered',"
        " start_date=%s, loan_end_date=NULL, role='substitute' WHERE player_id=%s",
        (lender, ret_date, player["player_id"]))
    seq, audit_id = _next_audit(conn)
    conn.execute(
        "INSERT INTO roster_audit (seq, audit_id, player_id, league_id, action, from_squad_id,"
        " to_squad_id, effective_date, state, who, \"when\", why)"
        " VALUES (%s,%s,%s,%s,'loan_return',%s,%s,%s,'active','system',%s,%s)",
        (seq, audit_id, player["player_id"], player["league_id"], borrower, lender, ret_date,
         utc_now_str(), "Automatic return after loan end date"))


def history(conn, player_id: str, as_of_raw: str | None) -> dict:
    if as_of_raw is None:
        as_of = datetime.now(timezone.utc).date()
    else:
        as_of = parse_date(as_of_raw)
        if as_of is None:
            raise validation_error(["as_of"], "as_of must be a date formatted YYYY-MM-DD.")
    row = conn.execute("SELECT league_id FROM roster_players WHERE player_id=%s", (player_id,)).fetchone()
    if row is None:
        raise DomainError(404, "PLAYER_NOT_FOUND", f"Player {player_id} does not exist.",
                          {"player_id": player_id})
    league_id = row["league_id"]
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("rl:" + league_id,))
    player = conn.execute("SELECT * FROM roster_players WHERE player_id=%s FOR UPDATE",
                          (player_id,)).fetchone()
    if (player["registration_type"] == "loan" and player["loan_end_date"] is not None
            and as_of > player["loan_end_date"]):
        _apply_loan_return(conn, player)          # exactly once: the state flip removes the loan

    entries = conn.execute("SELECT * FROM roster_audit WHERE player_id=%s ORDER BY seq",
                           (player_id,)).fetchall()
    base = conn.execute("SELECT initial_squad_id FROM roster_players WHERE player_id=%s",
                        (player_id,)).fetchone()["initial_squad_id"]
    current, parent = base, None
    for e in entries:                              # reads reflect the effective date
        if e["effective_date"] <= as_of:
            current = e["to_squad_id"]
            parent = e["from_squad_id"] if e["action"] == "loan" else None
    return {
        "player_id": player_id, "as_of": as_of.isoformat(), "league_id": league_id,
        "current_squad_id": current, "parent_squad_id": parent,
        "history": [_audit_json(e) for e in entries],
    }
