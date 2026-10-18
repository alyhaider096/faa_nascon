"""Cross-service lifecycle guarantees needed by Day 2 QR/VOD/overlay consumers."""
from copy import deepcopy

import pytest
from sqlalchemy import select

from backend.app.domain.common import DomainError
from backend.app.domain.models import Event, Outbox, ScheduledMatch
from backend.app.domain.scoring import append_event, project_score, register_league
from backend.app.domain.scheduling import reschedule, change_schedule_status
from backend.app.domain.standings import standings


def emit(session, sign, event_id, kind, payload=None):
    return append_event(session, {"event_id": event_id, "match_id": "handoff-match",
                                 "type": kind, "payload": payload or {}}, sign)


def prepare(session, sign):
    register_league(session, {"league_id": "handoff-league", "sport_id": "football",
        "teams": ["home", "away"], "fixtures": [{"match_id": "handoff-match", "home": "home", "away": "away"}],
        "qualification": {"spots": 1}})
    emit(session, sign, "start", "match_start")
    emit(session, sign, "goal", "score", {"team_id": "home", "event_type": "goal"})


def test_completion_replay_and_compensation_preserve_consumer_contract(session, sign):
    prepare(session, sign)
    before = standings(session, "handoff-league")
    assert all(row["played"] == 0 for row in before["table"])
    status, response = emit(session, sign, "end", "match_end")
    assert status == 201
    session.commit()
    session.expire_all()
    projection = project_score(session, "handoff-match")
    assert (projection["status"], projection["outcome"], projection["version"]) == ("completed", "home_win", 3)
    table = {row["team_id"]: row for row in standings(session, "handoff-league")["table"]}
    assert table["home"]["points"] == 3 and table["away"]["points"] == 0
    notifications = session.scalars(select(Outbox)).all()
    assert len(notifications) == 3
    assert emit(session, sign, "end", "match_end") == (200, response)
    assert len(session.scalars(select(Outbox)).all()) == 3
    original = deepcopy(session.get(Event, "goal").request)
    original_signature = session.get(Event, "goal").signature
    emit(session, sign, "correction", "compensation", {"compensates": "goal", "reason": "review"})
    session.commit()
    session.expire_all()
    corrected = project_score(session, "handoff-match")
    assert corrected["status"] == "completed" and corrected["outcome"] == "draw"
    assert corrected["home"]["score"] == 0 and corrected["version"] == 4
    assert session.get(Event, "goal").request == original
    assert session.get(Event, "goal").signature == original_signature
    assert {row["points"] for row in standings(session, "handoff-league")["table"]} == {1}


def test_completion_rollback_does_not_leave_notification_or_completed_score(session, sign):
    prepare(session, sign)
    session.commit()
    emit(session, sign, "end", "match_end")
    session.rollback()
    assert project_score(session, "handoff-match")["status"] == "in_progress"
    assert session.get(Event, "end") is None and session.get(Outbox, "end") is None


def test_postponement_is_separate_from_score_projection(session, sign):
    prepare(session, sign)
    schedule = {"venue_id": "v", "team_ids": ["home", "away"], "player_ids": [],
                "start": "2026-10-18T10:00:00Z", "end": "2026-10-18T11:00:00Z"}
    reschedule(session, "tenant", "handoff-match", schedule)
    reschedule(session, "tenant", "final", {**schedule, "start": "2026-10-18T12:00:00Z",
               "end": "2026-10-18T13:00:00Z", "depends_on": ["handoff-match"]})
    change_schedule_status(session, "tenant", "handoff-match", "in_progress")
    result = change_schedule_status(session, "tenant", "handoff-match", "postponed")
    session.commit()
    session.expire_all()
    assert result["downstream_reevaluation"] == ["final"]
    assert session.get(ScheduledMatch, "handoff-match").config["status"] == "postponed"
    assert session.get(ScheduledMatch, "final").config["needs_reevaluation"] is True
    assert project_score(session, "handoff-match")["status"] == "in_progress"
    with pytest.raises(DomainError) as exc:
        emit(session, sign, "invented", "match_postponed")
    assert exc.value.status == 400 and exc.value.code == "VALIDATION_ERROR"
