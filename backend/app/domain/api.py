"""Router factory; host injects its transaction dependency and startup signer."""
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from .common import DomainError, invalid
from .fixtures import generate_fixtures
from .scoring import append_event, project_score, register_league
from .sports import create_sport
from .standings import standings


async def read_body(request):
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > 1024 * 1024:
            raise DomainError(413, 'PAYLOAD_TOO_LARGE')
    try:
        return json.loads(chunks.decode('utf-8'), parse_constant=lambda _: invalid('body'))
    except (ValueError, UnicodeError):
        invalid('body')


def build_router(get_session, sign_record):
    router = APIRouter(prefix='/audit/v1')

    @router.post('/sports')
    async def sports_route(request: Request, session=Depends(get_session)):
        body = await read_body(request)
        result = await run_in_threadpool(create_sport, session, body)
        return JSONResponse(result, status_code=201)

    @router.post('/fixtures')
    async def fixtures_route(request: Request):
        return await run_in_threadpool(generate_fixtures, await read_body(request))

    @router.post('/leagues')
    async def leagues_route(request: Request, session=Depends(get_session)):
        result = await run_in_threadpool(register_league, session, await read_body(request))
        return JSONResponse(result, status_code=201)

    @router.post('/events')
    async def events_route(request: Request, session=Depends(get_session)):
        status, result = await run_in_threadpool(append_event, session, await read_body(request), sign_record)
        return JSONResponse(result, status_code=status)

    @router.get('/score/{match_id}')
    def score_route(match_id: str, session=Depends(get_session)):
        return project_score(session, match_id)

    @router.get('/standings/{league_id}')
    def standings_route(league_id: str, session=Depends(get_session)):
        return standings(session, league_id)

    return router


async def domain_error_handler(request, exc):
    return JSONResponse(exc.body(), status_code=exc.status)
