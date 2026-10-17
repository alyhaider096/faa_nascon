"""Mandatory autograder surface owned by the platform side: health, reset, roster, store, RBAC
probes and offline sync. Scoring/standings/fixtures routes live in the domain owner's router
(`app.api.domain_audit`, mounted automatically when present)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..core import queue
from ..core.config import get_settings
from ..core.db import tx
from ..core.errors import DomainError
from ..core.security import (authenticate, can_edit_player, can_manage_club, can_manage_league,
                             can_read_club, forbidden, issue_token, role_may_ever)
from ..core.validation import read_json_object
from ..domain import offline, roster, seed as seed_mod, store
from .common import run_tx

router = APIRouter()


@router.get("/health")
def health():
    try:
        with tx() as conn:
            ok = seed_mod.is_seeded(conn)
    except Exception:  # noqa: BLE001 - any DB trouble means "not ready"
        ok = False
    if not ok:
        return JSONResponse(status_code=503, content={"status": "starting"})
    return {"status": "ok"}


# ---------------------------------------------------------------------------- reset ---------
@router.post("/audit/v1/reset")
async def reset(request: Request):
    body = await read_json_object(request, required=False)
    seed, stock = seed_mod.parse_reset_body(body)
    out = await run_tx(seed_mod.reset, seed, stock)
    out.pop("_hooks", None)
    await run_in_threadpool(queue.clear_all, get_settings().redis_url)
    return out


# --------------------------------------------------------------------------- roster ---------
@router.post("/audit/v1/roster/setup")
async def roster_setup(request: Request):
    body = await read_json_object(request)
    return JSONResponse(status_code=201, content=await run_tx(roster.setup, body))


@router.post("/audit/v1/roster/transfer")
async def roster_transfer(request: Request):
    body = await read_json_object(request)
    status, out = await run_tx(roster.transfer, body)
    return JSONResponse(status_code=status, content=out)


@router.get("/audit/v1/roster/history/{player_id}")
async def roster_history(player_id: str, as_of: str | None = None):
    return await run_tx(roster.history, player_id, as_of)


# ---------------------------------------------------------------------------- store ---------
@router.post("/audit/v1/checkout")
async def checkout(request: Request):
    body = await read_json_object(request)
    status, out = await run_tx(store.checkout, body)
    return JSONResponse(status_code=status, content=out)


@router.get("/audit/v1/inventory/{variant_id}")
async def inventory(variant_id: str):
    return await run_tx(store.inventory, variant_id)


# ------------------------------------------------------------------------ offline sync ------
@router.post("/audit/v1/offline-sync")
async def offline_sync(request: Request):
    body = await read_json_object(request)
    return await run_tx(offline.sync, body)


# ----------------------------------------------------------------------------- RBAC ---------
_MATRIX_USERS = (("super_admin", "admin@nascon.test"), ("league_organizer", "organizer@nascon.test"),
                 ("club_manager", "manager@nascon.test"), ("player", "player@nascon.test"),
                 ("viewer", "viewer@nascon.test"))


def _matrix(conn) -> dict:
    tokens = {}
    for key, email in _MATRIX_USERS:
        user = conn.execute("SELECT * FROM users WHERE email=%s", (email,)).fetchone()
        if user is None:
            raise DomainError(503, "NOT_SEEDED", "Baseline data is not seeded yet.")
        tokens[key] = issue_token(user, ttl=2 * 3600)
    return {
        "tokens": tokens,
        "context": {
            "tenant_id": "tenant-alpha", "foreign_tenant_id": "tenant-beta",
            "own_league_id": "league-alpha-1", "other_league_id": "league-alpha-2",
            "foreign_league_id": "league-beta-1",
            "own_club_id": "club-alpha-1", "other_club_id": "club-alpha-2", "foreign_club_id": "club-beta-1",
            "own_player_id": "player-alpha-1", "other_player_id": "player-alpha-2",
            "foreign_player_id": "player-beta-1",
        },
    }


@router.post("/audit/v1/rbac-matrix")
async def rbac_matrix():
    return await run_tx(_matrix)


def _ok() -> dict:
    return {"authorized": True}


def _lookup(sql: str, key: str, code: str, label: str):
    with tx() as conn:
        row = conn.execute(sql, (key,)).fetchone()
    if row is None:
        raise DomainError(404, code, f"{label} {key} does not exist.", {"id": key})
    return row


# Probes only authorize: they never read or validate the request body and never mutate.
# Order: authenticate (401) -> role gate (403) -> existence (404) -> scope/tenant (403).
@router.post("/audit/v1/rbac/tenants")
def probe_tenants(request: Request):
    claims = authenticate(request)
    if not role_may_ever(claims, "tenants"):
        raise forbidden()
    return _ok()


@router.post("/audit/v1/rbac/leagues/{league_id}/fixtures")
def probe_league_fixtures(league_id: str, request: Request):
    claims = authenticate(request)
    if not role_may_ever(claims, "league_fixtures"):
        raise forbidden()
    league = _lookup("SELECT * FROM ref_leagues WHERE league_id=%s", league_id, "LEAGUE_NOT_FOUND", "League")
    if not can_manage_league(claims, league):
        raise forbidden()
    return _ok()


@router.post("/audit/v1/rbac/clubs/{club_id}/roster")
def probe_club_roster(club_id: str, request: Request):
    return _probe_club_manage(club_id, request, "club_roster")


@router.post("/audit/v1/rbac/clubs/{club_id}/products")
def probe_club_products(club_id: str, request: Request):
    return _probe_club_manage(club_id, request, "club_products")


def _probe_club_manage(club_id: str, request: Request, probe: str):
    claims = authenticate(request)
    if not role_may_ever(claims, probe):
        raise forbidden()
    club = _lookup("SELECT * FROM ref_clubs WHERE club_id=%s", club_id, "CLUB_NOT_FOUND", "Club")
    if not can_manage_club(claims, club):
        raise forbidden()
    return _ok()


@router.patch("/audit/v1/rbac/players/{player_id}")
def probe_player_update(player_id: str, request: Request):
    claims = authenticate(request)
    if not role_may_ever(claims, "player_update"):
        raise forbidden()
    player = _lookup("SELECT * FROM ref_players WHERE player_id=%s", player_id, "PLAYER_NOT_FOUND", "Player")
    if not can_edit_player(claims, player):
        raise forbidden()
    return _ok()


@router.get("/audit/v1/rbac/clubs/{club_id}")
def probe_club_read(club_id: str, request: Request):
    claims = authenticate(request)
    club = _lookup("SELECT * FROM ref_clubs WHERE club_id=%s", club_id, "CLUB_NOT_FOUND", "Club")
    if not can_read_club(claims, club):
        raise forbidden()
    return _ok()


@router.get("/audit/v1/rbac/platform/config")
def probe_platform_config(request: Request):
    claims = authenticate(request)
    if not role_may_ever(claims, "platform_config"):
        raise forbidden()
    return _ok()
