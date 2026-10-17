"""Adapter between the platform's psycopg transactions and the scoring/standings/fixtures services.

This module is the one place that knows both worlds; it satisfies the frozen port in
`app.core.ports` (conn-based) and exposes the HTTP-facing calls used by the routers.
"""
from __future__ import annotations

from ..core import sa
from ..core.errors import DomainError
from ..core.signing import sign_record
from . import common as _c
from . import fixtures as _fixtures
from . import scoring as _scoring
from . import seeds as _seeds
from . import sports as _sports
from . import standings as _standings
from .models import Event, Match


def _translate(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except _c.DomainError as exc:
        raise DomainError(exc.status, exc.code, exc.message, exc.details) from None


# -------------------------------------------------------------------- frozen port ---------
def get_match_version(conn, match_id):
    with sa.session(conn) as s:
        if s.get(Match, match_id) is None:
            return None
        return _translate(_scoring.get_match_version, s, match_id)


def find_event(conn, event_id):
    with sa.session(conn) as s:
        ev = s.get(Event, event_id)
        return None if ev is None else dict(ev.request)


def match_league_id(conn, match_id):
    with sa.session(conn) as s:
        m = s.get(Match, match_id)
        return None if m is None else m.league_id


def append_event(conn, body):
    with sa.session(conn) as s:
        status, resp = _translate(_scoring.append_event, s, body, sign_record)
    return ("replay" if status == 200 else "new"), resp


def reset(conn, seed):
    with sa.session(conn) as s:
        _seeds.reset_domain(s, seed)


# ------------------------------------------------------------------- http-facing ----------
def create_sport(conn, body):
    with sa.session(conn) as s:
        return _translate(_sports.create_sport, s, body)


def generate_fixtures(body):
    return _translate(_fixtures.generate_fixtures, body)


def register_league(conn, body):
    with sa.session(conn) as s:
        return _translate(_scoring.register_league, s, body)


def project_score(conn, match_id):
    with sa.session(conn) as s:
        return _translate(_scoring.project_score, s, match_id)


def standings(conn, league_id):
    with sa.session(conn) as s:
        return _translate(_standings.standings, s, league_id)
