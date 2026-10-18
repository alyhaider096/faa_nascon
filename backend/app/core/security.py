"""JWT issuing/verification, password hashing, and the five-role policy matrix (Section 5.13).

Tokens are HS256 with a key derived from DAY1_SALT (the salt itself is never a token key,
never logged, never exposed). The algorithm allowlist is exactly ["HS256"], so alg:none,
RS/ES confusion and tampered signatures all fail with 401.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from starlette.requests import Request

from .config import get_settings
from .errors import DomainError

ROLES = ("super_admin", "league_organizer", "club_manager", "player", "viewer")


def _unauth(message: str = "Authentication required.") -> DomainError:
    return DomainError(401, "UNAUTHENTICATED", message, headers={"WWW-Authenticate": "Bearer"})


def forbidden(message: str = "You are not allowed to perform this action.",
              details: dict | None = None) -> DomainError:
    return DomainError(403, "FORBIDDEN", message, details or {})


@lru_cache(maxsize=1)
def _jwt_key_for(salt: str) -> bytes:
    return hmac.new(salt.encode("utf-8"), b"nascon/jwt-signing-key/v1", hashlib.sha256).digest()


def _jwt_key() -> bytes:
    return _jwt_key_for(get_settings().day1_salt)


def issue_token(user: dict, *, ttl: int | None = None) -> str:
    now = int(time.time())
    claims = {
        "sub": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "tenant_id": user.get("tenant_id"),
        "league_id": user.get("league_id"),
        "club_id": user.get("club_id"),
        "player_id": user.get("player_id"),
        "ver": int(user.get("token_version", 0)),
        "iat": now,
        "exp": now + (ttl if ttl is not None else get_settings().token_ttl_seconds),
    }
    return jwt.encode(claims, _jwt_key(), algorithm="HS256")


@dataclass(frozen=True)
class Claims:
    user_id: str
    email: str
    role: str
    tenant_id: str | None
    league_id: str | None
    club_id: str | None
    player_id: str | None
    token_version: int


def decode_token(token: str) -> Claims:
    try:
        data = jwt.decode(
            token, _jwt_key(), algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub", "role"], "verify_signature": True,
                     "verify_exp": True},
        )
    except jwt.PyJWTError:
        raise _unauth("Invalid, expired or tampered token.")
    if data.get("role") not in ROLES:
        raise _unauth("Invalid token.")
    return Claims(
        user_id=str(data["sub"]), email=str(data.get("email", "")), role=data["role"],
        tenant_id=data.get("tenant_id"), league_id=data.get("league_id"),
        club_id=data.get("club_id"), player_id=data.get("player_id"),
        token_version=int(data.get("ver", 0)),
    )


def validate_active_claims(claims: Claims) -> Claims:
    """Reject a validly signed JWT after its account has been erased/revoked."""
    from .db import tx

    with tx() as conn:
        row = conn.execute("SELECT token_version FROM users WHERE user_id=%s", (claims.user_id,)).fetchone()
    if row is None or row["token_version"] != claims.token_version:
        raise _unauth("Token has been revoked.")
    return claims


def authenticate_token(token: str) -> Claims:
    return validate_active_claims(decode_token(token))


def authenticate(request: Request) -> Claims:
    header = request.headers.get("authorization")
    if not header:
        raise _unauth()
    parts = header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise _unauth("Malformed Authorization header.")
    return authenticate_token(parts[1])


def reject_anonymous_guest(request: Request) -> None:
    """Enforce the Phase II read-only guest boundary before a mutation parses its body."""
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else ""
    if token.startswith("guest_"):
        raise DomainError(
            403, "GUEST_WRITE_FORBIDDEN",
            "Anonymous guest tokens cannot perform write mutations.",
            {"guest_token": token},
        )


# Passwords ---------------------------------------------------------------------------------
_PBKDF2_ROUNDS = 60_000


@lru_cache(maxsize=64)
def hash_password(password: str, salt_hint: str) -> str:
    """Deterministic per-user hash (salt = the user's email) so every reset seeds identical rows."""
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 ("nascon-pw:" + salt_hint).encode("utf-8"), _PBKDF2_ROUNDS)
    return "pbkdf2$" + str(_PBKDF2_ROUNDS) + "$" + digest.hex()


def verify_password(password: str, salt_hint: str, stored: str) -> bool:
    candidate = hash_password(password, salt_hint)
    return hmac.compare_digest(candidate, stored)


# Policy ------------------------------------------------------------------------------------
def is_super(c: Claims) -> bool:
    return c.role == "super_admin"


def can_read_club(c: Claims, club: dict) -> bool:
    """P6: any role inside the tenant reads; foreign tenant only for the super admin."""
    return is_super(c) or c.tenant_id == club["tenant_id"]


def can_manage_league(c: Claims, league: dict) -> bool:
    """P2: super admin anywhere; an organizer only the league they own."""
    if is_super(c):
        return True
    return c.role == "league_organizer" and c.league_id == league["league_id"] \
        and c.tenant_id == league["tenant_id"]


def can_manage_club(c: Claims, club: dict) -> bool:
    """P3/P4: super admin anywhere; a manager only their own club."""
    if is_super(c):
        return True
    return c.role == "club_manager" and c.club_id == club["club_id"] and c.tenant_id == club["tenant_id"]


def can_edit_player(c: Claims, player: dict) -> bool:
    """P5: super admin; a manager for players of their own club; a player only themselves."""
    if is_super(c):
        return True
    if c.role == "club_manager":
        return c.club_id == player["club_id"] and c.tenant_id == player["tenant_id"]
    if c.role == "player":
        return c.player_id == player["player_id"] and c.tenant_id == player["tenant_id"]
    return False


def role_may_ever(c: Claims, probe: str) -> bool:
    """Coarse per-route role gate evaluated before any existence lookup (so e.g. a viewer
    probing a non-existent league still gets 403, not 404)."""
    allowed: dict[str, tuple[str, ...]] = {
        "tenants": ("super_admin",),
        "platform_config": ("super_admin",),
        "league_fixtures": ("super_admin", "league_organizer"),
        "club_roster": ("super_admin", "club_manager"),
        "club_products": ("super_admin", "club_manager"),
        "player_update": ("super_admin", "club_manager", "player"),
        "club_read": ROLES,
    }
    return c.role in allowed[probe]


def claims_public(c: Claims) -> dict[str, Any]:
    return {"user_id": c.user_id, "email": c.email, "role": c.role, "tenant_id": c.tenant_id,
            "league_id": c.league_id, "club_id": c.club_id, "player_id": c.player_id}
