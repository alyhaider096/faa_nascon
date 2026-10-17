"""Authenticated mobile reads and scoring over the domain services (same services as /audit/v1)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..core import ports, realtime
from ..core.db import tx
from ..core.errors import DomainError
from ..core.security import authenticate, forbidden, is_super
from ..core.validation import read_json_object
from ..domain import bridge
from .common import run_tx
from .domain_audit import append_and_notify

router = APIRouter(prefix="/api/v1")


def _league_scope(conn, claims, league_id: str) -> None:
    """Leagues known to the tenant registry are tenant-scoped; audit-registered ones are open to
    any authenticated user (they carry no tenant)."""
    row = conn.execute("SELECT tenant_id FROM ref_leagues WHERE league_id=%s", (league_id,)).fetchone()
    if row is not None and not is_super(claims) and row["tenant_id"] != claims.tenant_id:
        raise forbidden()


@router.get("/leagues/{league_id}/standings")
def league_standings(league_id: str, request: Request):
    claims = authenticate(request)
    with tx() as conn:
        _league_scope(conn, claims, league_id)
        return bridge.standings(conn, league_id)


@router.get("/matches/{match_id}")
def match_detail(match_id: str, request: Request):
    authenticate(request)
    with tx() as conn:
        return bridge.project_score(conn, match_id)


@router.post("/fixtures/preview")
async def fixtures_preview(request: Request):
    authenticate(request)
    return bridge.generate_fixtures(await read_json_object(request))


@router.post("/matches/{match_id}/events")
async def post_event(match_id: str, request: Request):
    """Score/discipline/compensation etc. Organizer for the match's league, or super admin."""
    claims = authenticate(request)
    body = await read_json_object(request)
    body = {**body, "match_id": body.get("match_id", match_id)}
    if body["match_id"] != match_id:
        raise DomainError(400, "VALIDATION_ERROR", "match_id in body differs from the URL.",
                          {"fields": ["match_id"]})
    if not is_super(claims):
        if claims.role != "league_organizer":
            raise forbidden()

        def check(conn):
            league = bridge.match_league_id(conn, match_id)
            if league is None:
                payload = body.get("payload")
                league = payload.get("league_id") if isinstance(payload, dict) else None
            if league != claims.league_id:
                raise forbidden()
        await run_tx(check)
    kind, resp = await append_and_notify(body)
    return JSONResponse(resp, status_code=201 if kind == "new" else 200)
