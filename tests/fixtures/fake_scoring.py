"""In-memory stand-in for the scoring owner's `app.domain.scoring` port, used ONLY by platform
tests (offline coordinator). It implements the frozen interface from app/core/ports.py and signs
through the shared helper. The real scoring engine is a separate module and is not duplicated here.
"""
from __future__ import annotations

import copy

from app.core.errors import DomainError
from app.core.signing import sign_record


class FakeScoring:
    def __init__(self) -> None:
        self.matches: dict[str, dict] = {}
        self.events: dict[str, dict] = {}

    # -- frozen port ------------------------------------------------------------------------
    def reset(self, conn, seed):
        self.matches.clear()
        self.events.clear()

    def get_match_version(self, conn, match_id):
        m = self.matches.get(match_id)
        return None if m is None else len(m["log"])

    def find_event(self, conn, event_id):
        e = self.events.get(event_id)
        return None if e is None else copy.deepcopy(e["body"])

    def match_league_id(self, conn, match_id):
        m = self.matches.get(match_id)
        return None if m is None else m.get("league_id")

    def append_event(self, conn, body):
        event_id, match_id, typ, payload = body["event_id"], body["match_id"], body["type"], body["payload"]
        prior = self.events.get(event_id)
        if prior is not None:
            if prior["body"] == body:
                return "replay", prior["response"]
            raise DomainError(409, "DUPLICATE_EVENT_ID", "event_id reused with a different body")
        m = self.matches.get(match_id)
        if typ == "match_init":
            if m is not None:
                raise DomainError(409, "MATCH_EXISTS", "match exists")
            m = self.matches[match_id] = {"status": "upcoming", "log": [], "league_id": payload.get("league_id")}
        elif m is None:
            raise DomainError(404, "MATCH_NOT_FOUND", "no such match")
        elif typ == "match_start":
            if m["status"] != "upcoming":
                raise DomainError(409, "ILLEGAL_TRANSITION", "bad transition")
            m["status"] = "in_progress"
        elif typ == "score":
            if m["status"] != "in_progress":
                raise DomainError(409, "MATCH_NOT_IN_PROGRESS", "not in progress")
        elif typ == "compensation":
            target = self.events.get(payload.get("compensates"))
            if target is None:
                raise DomainError(404, "EVENT_NOT_FOUND", "no such event")
            if target["compensated"] or target["match_id"] != match_id:
                raise DomainError(409, "INVALID_COMPENSATION", "invalid compensation")
            target["compensated"] = True
        m["log"].append(event_id)
        response = {"event_id": event_id, "match_id": match_id, "type": typ, "sequence": len(m["log"]),
                    "match_version": len(m["log"]), "signature": sign_record(event_id, payload)}
        self.events[event_id] = {"body": copy.deepcopy(body), "response": response,
                                 "match_id": match_id, "compensated": False}
        return "new", response
