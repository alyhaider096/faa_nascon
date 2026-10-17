"""Frozen integration points between platform code and the scoring/standings/fixtures owner.

Platform code never re-implements those domains. It looks for these functions in the module
`app.domain.bridge` (adapter over the scoring module; or an injected port in tests). All of them receive the *caller's* open
psycopg connection, so nothing here commits: the offline coordinator owns the transaction and
savepoint boundaries.

    get_match_version(conn, match_id) -> int | None
        Number of events in the match log; None when the stream does not exist.

    find_event(conn, event_id) -> dict | None
        The stored request body {"event_id","match_id","type","payload"} for an existing
        event_id, else None.

    append_event(conn, body) -> tuple[str, dict]
        ("new" | "replay", exact /audit/v1/events response). Raises DomainError with the exact
        Appendix B code for every rule failure. Must sign through app.core.signing.sign_record
        and must not commit.

    match_league_id(conn, match_id) -> str | None            (optional; used for authorization)

    reset(conn, seed) -> None                                (optional; registered reset hook)
"""
from __future__ import annotations

import importlib
from typing import Any

from .errors import DomainError

_scoring_override: Any = None

RESET_HOOK_MODULES = (
    "app.domain.bridge",
)


def set_scoring(port: Any) -> None:
    """Test hook / explicit wiring."""
    global _scoring_override
    _scoring_override = port


def scoring() -> Any:
    if _scoring_override is not None:
        return _scoring_override
    try:
        return importlib.import_module("app.domain.bridge")
    except ModuleNotFoundError:
        raise DomainError(
            501, "NOT_IMPLEMENTED",
            "The scoring module is not installed in this build.", {"module": "app.domain.scoring"},
        )


def run_reset_hooks(conn, seed: int) -> list[str]:
    """Call `reset(conn, seed)` on every domain module that provides one."""
    ran: list[str] = []
    for name in RESET_HOOK_MODULES:
        try:
            mod = importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        hook = getattr(mod, "reset", None)
        if callable(hook):
            hook(conn, seed)
            ran.append(name)
    if _scoring_override is not None and callable(getattr(_scoring_override, "reset", None)):
        _scoring_override.reset(conn, seed)
        ran.append("<injected scoring port>")
    return ran
