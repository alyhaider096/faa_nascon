"""Small helpers shared by the route modules."""
from __future__ import annotations

from typing import Any, Callable

from starlette.concurrency import run_in_threadpool

from ..core.db import tx


async def run_tx(fn: Callable[..., Any], *args: Any) -> Any:
    """Run `fn(conn, *args)` in a worker thread inside ONE database transaction."""
    def work():
        with tx() as conn:
            return fn(conn, *args)
    return await run_in_threadpool(work)
