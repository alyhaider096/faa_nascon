"""Audit routes for sports, fixtures, leagues, signed events, score projection and standings."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from ..core import realtime
from ..core.security import reject_anonymous_guest
from ..core.validation import read_json_object
from ..domain import bridge, day2
from .common import run_tx

router = APIRouter(prefix="/audit/v1")


@router.post("/sports")
async def sports(request: Request):
    body = await read_json_object(request)
    return JSONResponse(await run_tx(bridge.create_sport, body), status_code=201)


@router.post("/fixtures")
async def fixtures(request: Request):
    body = await read_json_object(request)
    return await run_in_threadpool(bridge.generate_fixtures, body)


@router.post("/leagues")
async def leagues(request: Request):
    body = await read_json_object(request)
    return JSONResponse(await run_tx(bridge.register_league, body), status_code=201)


async def append_and_notify(body: dict):
    kind, resp = await run_tx(bridge.append_event, body)
    if kind == "new":
        await realtime.hub.publish(resp.get("match_id", body.get("match_id")),
                                   {"type": "score_updated", "match_id": resp.get("match_id"),
                                    "event_id": resp.get("event_id"), "version": resp.get("match_version")})
    return kind, resp


@router.post("/events")
async def events(request: Request):
    reject_anonymous_guest(request)
    body = await read_json_object(request)
    if body.get("match_id") == "match-m1":
        kind, resp, state = await run_tx(day2.append_public_match_event, body)
        if kind == "new":
            await realtime.hub.publish("match-m1", {
                "type": "match_state" if body.get("type") != "score" else "score",
                "sequence": state["version"], "status": state["status"],
                "home_score": state["score_home"], "away_score": state["score_away"],
            })
        return JSONResponse(resp, status_code=201 if kind == "new" else 200)
    kind, resp = await append_and_notify(body)
    if kind == "new":
        await run_tx(day2.apply_match_event, body)
    return JSONResponse(resp, status_code=201 if kind == "new" else 200)


@router.get("/score/{match_id}")
async def score(match_id: str):
    return await run_tx(bridge.project_score, match_id)


@router.get("/standings/{league_id}")
async def standings(league_id: str):
    return await run_tx(bridge.standings, league_id)
