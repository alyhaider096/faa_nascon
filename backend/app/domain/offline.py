"""Offline sync coordinator (Section 5.14).

One request = one transaction. Every action runs in its own SAVEPOINT so a failing action cannot
corrupt later ones, and *every* processed action (applied, duplicate or rejected) is persisted
under (device_id, action_id), so re-sending the same request makes every action a duplicate and
changes nothing. The whole request holds one advisory lock, so concurrent syncs (and their
dedup keys) are serialised atomically.

Precedence for a single action (first match wins):
  1. (device_id, action_id) already processed                       -> duplicate / skipped_duplicate
  2. score_event: same event_id already stored with identical body   -> duplicate / skipped_duplicate
     roster_transfer: same request_id already stored, identical body -> duplicate / skipped_duplicate
  3. referenced ids missing                                          -> rejected / server_wins / *_NOT_FOUND
  4. conflicting event_id (other body)                               -> rejected / server_wins / DUPLICATE_EVENT_ID
  5. base_version > current version                                  -> rejected / server_wins / INVALID_BASE_VERSION
  6. domain rules reject                                             -> rejected / server_wins / <rule code>
  7. applied: base_version == current -> appended, base_version < current -> rebased_append
Actions are processed sorted by (queued_at, input index) but results are returned in request order.
"""
from __future__ import annotations

from typing import Any, Callable

from psycopg.types.json import Jsonb

from ..core import ports
from ..core.errors import DomainError, validation_error
from ..core.signing import request_hash
from ..core.validation import Fields, is_id, is_int, parse_ts
from . import roster

ACTION_TYPES = ("score_event", "roster_transfer")
MAX_ACTIONS = 100

Authorizer = Callable[[dict], None]


def _validate_envelope(body: dict) -> tuple[str, list[dict]]:
    f = Fields()
    device_id = f.need_id(body, "device_id")
    actions = body.get("actions")
    parsed: list[dict] = []
    if not isinstance(actions, list) or not (1 <= len(actions) <= MAX_ACTIONS):
        f.add("actions")
    else:
        for i, a in enumerate(actions):
            if not isinstance(a, dict):
                f.add(f"actions[{i}]")
                f.add("actions")
                continue
            aid = a.get("action_id")
            if not is_id(aid):
                f.add(f"actions[{i}].action_id")
                f.add("action_id")
            if a.get("type") not in ACTION_TYPES:
                f.add(f"actions[{i}].type")
                f.add("type")
            ts = parse_ts(a.get("queued_at"))
            if ts is None:
                f.add(f"actions[{i}].queued_at")
                f.add("queued_at")
            bv = a.get("base_version")
            if not is_int(bv) or bv < 0:
                f.add(f"actions[{i}].base_version")
                f.add("base_version")
            if not isinstance(a.get("payload"), dict):
                f.add(f"actions[{i}].payload")
                f.add("payload")
            parsed.append({"index": i, "action_id": aid, "type": a.get("type"), "queued_at": ts,
                           "base_version": bv, "payload": a.get("payload")})
    f.check()
    return device_id, parsed


def _result(action_id: str, status: str, resolution: str, code: str | None, order: int,
            version: int, signature: str | None) -> dict:
    return {"action_id": action_id, "status": status, "resolution": resolution, "error_code": code,
            "processed_order": order, "server_version": version, "signature": signature}


def _event_identity(body: dict) -> str:
    return request_hash({"event_id": body.get("event_id"), "match_id": body.get("match_id"),
                         "type": body.get("type"), "payload": body.get("payload")})


class _Outcome(Exception):
    """Internal control flow carrying a finished per-action outcome."""

    def __init__(self, status: str, resolution: str, code: str | None, version: int,
                 signature: str | None = None):
        super().__init__(status)
        self.status, self.resolution, self.code = status, resolution, code
        self.version, self.signature = version, signature


def _rejected(code: str, version: int) -> _Outcome:
    return _Outcome("rejected", "server_wins", code, version)


def _duplicate(version: int) -> _Outcome:
    return _Outcome("duplicate", "skipped_duplicate", None, version)


def _score_version(conn, match_id: Any) -> int:
    if not is_id(match_id):
        return 0
    return ports.scoring().get_match_version(conn, match_id) or 0


def _roster_version(conn, player_id: Any) -> int:
    if not is_id(player_id):
        return 0
    return roster.player_version(conn, player_id) or 0


def _apply_score(conn, a: dict) -> _Outcome:
    body = a["payload"]
    sc = ports.scoring()
    f = Fields()
    event_id = f.need_id(body, "event_id")
    match_id = f.need_id(body, "match_id")
    if not isinstance(body.get("type"), str) or not body.get("type"):
        f.add("type")
    if not isinstance(body.get("payload"), dict):
        f.add("payload")
    if f.bad:
        raise _rejected("VALIDATION_ERROR", 0)

    existing = sc.find_event(conn, event_id)
    cur = sc.get_match_version(conn, match_id)
    if existing is not None:
        if _event_identity(existing) == _event_identity(body):
            raise _duplicate(cur or 0)
        raise _rejected("DUPLICATE_EVENT_ID", cur or 0)
    if cur is None:
        if body["type"] != "match_init":
            raise _rejected("MATCH_NOT_FOUND", 0)
        cur = 0
    if a["base_version"] > cur:
        raise _rejected("INVALID_BASE_VERSION", cur)
    try:
        status, resp = sc.append_event(conn, body)
    except DomainError as exc:
        raise _rejected(exc.code, _score_version(conn, match_id))
    if status == "replay":
        raise _duplicate(resp.get("match_version", cur))
    resolution = "appended" if a["base_version"] == cur else "rebased_append"
    return _Outcome("applied", resolution, None, resp["match_version"], resp.get("signature"))


def _apply_roster(conn, a: dict) -> _Outcome:
    body = a["payload"]
    try:
        v = roster.validate_transfer(body)
    except DomainError:
        raise _rejected("VALIDATION_ERROR", _roster_version(conn, body.get("player_id")))
    prior = roster.find_request(conn, v["request_id"])
    if prior is not None:
        if prior["body_hash"] == v["_hash"]:
            raise _duplicate(_roster_version(conn, v["player_id"]))
        raise _rejected("DUPLICATE_REQUEST_ID", _roster_version(conn, v["player_id"]))
    try:
        roster.check_references(conn, v)
    except DomainError as exc:
        raise _rejected(exc.code, _roster_version(conn, v["player_id"]))
    cur = _roster_version(conn, v["player_id"])
    if a["base_version"] > cur:
        raise _rejected("INVALID_BASE_VERSION", cur)
    try:
        status, resp = roster.transfer(conn, body)
    except DomainError as exc:
        raise _rejected(exc.code, cur)
    if status == 200:
        raise _duplicate(_roster_version(conn, v["player_id"]))
    resolution = "appended" if a["base_version"] == cur else "rebased_append"
    return _Outcome("applied", resolution, None, _roster_version(conn, v["player_id"]))


def _current_version(conn, a: dict) -> int:
    p = a["payload"]
    if a["type"] == "score_event":
        try:
            return _score_version(conn, p.get("match_id"))
        except DomainError:
            return 0
    return _roster_version(conn, p.get("player_id"))


def sync(conn, body: dict, *, authorize: Authorizer | None = None) -> dict:
    device_id, actions = _validate_envelope(body)
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("offline-sync",))

    order = sorted(actions, key=lambda a: (a["queued_at"], a["index"]))
    results: list[dict | None] = [None] * len(actions)
    for pos, a in enumerate(order, start=1):
        prior = conn.execute("SELECT 1 FROM offline_actions WHERE device_id=%s AND action_id=%s",
                             (device_id, a["action_id"])).fetchone()
        if prior is not None:
            res = _result(a["action_id"], "duplicate", "skipped_duplicate", None, pos,
                          _current_version(conn, a), None)
            results[a["index"]] = res
            continue
        try:
            with conn.transaction():              # SAVEPOINT: a failing action leaves no trace
                if authorize is not None:
                    authorize(a)
                outcome = _apply_score(conn, a) if a["type"] == "score_event" else _apply_roster(conn, a)
        except _Outcome as o:
            outcome = o
        except DomainError as exc:                # e.g. 403 from the authorizer, 501 scoring missing
            outcome = _rejected(exc.code, _current_version(conn, a))
        res = _result(a["action_id"], outcome.status, outcome.resolution, outcome.code, pos,
                      outcome.version, outcome.signature if outcome.status == "applied" else None)
        # NOTE: an _Outcome raised inside the savepoint block rolled its writes back; "applied" is
        # returned (not raised) so it is the only outcome whose writes are kept.
        conn.execute(
            "INSERT INTO offline_actions (device_id, action_id, action_type, result) VALUES (%s,%s,%s,%s)",
            (device_id, a["action_id"], a["type"], Jsonb(res)))
        results[a["index"]] = res

    final = [r for r in results if r is not None]
    summary = {"applied": 0, "rejected": 0, "duplicate": 0}
    for r in final:
        summary[r["status"]] += 1
    return {"device_id": device_id, "results": final, "summary": summary}
