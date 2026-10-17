"""Authenticated mobile/product API under /api/v1/*. Same domain services as the audit wrappers,
with real authentication and the identical scoped policy (auth first: 401 -> 403 -> 404/409)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..core import ports, realtime
from ..core.db import tx
from ..core.errors import DomainError, validation_error
from ..core.security import (Claims, authenticate, claims_public, forbidden, is_super, issue_token,
                             verify_password)
from ..core.validation import Fields, is_id, read_json_object
from ..domain import offline, roster, store
from .common import run_tx

router = APIRouter(prefix="/api/v1")


@router.get("/ping")
def ping():
    """Rate-limit probe (unauthenticated on purpose)."""
    return {"pong": True}


# ------------------------------------------------------------------------------ auth --------
@router.post("/auth/login")
async def login(request: Request):
    body = await read_json_object(request)
    f = Fields()
    email, password = body.get("email"), body.get("password")
    if not isinstance(email, str) or not email or len(email) > 200:
        f.add("email")
    if not isinstance(password, str) or not password or len(password) > 200:
        f.add("password")
    f.check()

    def work(conn):
        user = conn.execute("SELECT * FROM users WHERE email=%s", (email.lower(),)).fetchone()
        if user is None or not verify_password(password, user["email"], user["password_hash"]):
            raise DomainError(401, "UNAUTHENTICATED", "Invalid email or password.")
        tenant = conn.execute("SELECT tenant_id, name, branding FROM tenants WHERE tenant_id=%s",
                              (user["tenant_id"],)).fetchone() if user["tenant_id"] else None
        return {"token": issue_token(user), "token_type": "Bearer",
                "user": _user_json(user), "tenant": tenant}
    return await run_tx(work)


def _user_json(user: dict) -> dict:
    return {"user_id": user["user_id"], "email": user["email"], "role": user["role"],
            "display_name": user["display_name"], "tenant_id": user["tenant_id"],
            "league_id": user["league_id"], "club_id": user["club_id"], "player_id": user["player_id"]}


@router.get("/me")
def me(request: Request):
    claims = authenticate(request)
    with tx() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=%s", (claims.user_id,)).fetchone()
        if user is None:
            raise DomainError(401, "UNAUTHENTICATED", "Account no longer exists.")
        tenant = conn.execute("SELECT tenant_id, name, branding FROM tenants WHERE tenant_id=%s",
                              (user["tenant_id"],)).fetchone() if user["tenant_id"] else None
    return {"user": _user_json(user), "tenant": tenant}


@router.get("/bootstrap")
def bootstrap(request: Request):
    """One call after login: profile, tenant branding, visible leagues/clubs and the catalogue."""
    claims = authenticate(request)
    with tx() as conn:
        user = conn.execute("SELECT * FROM users WHERE user_id=%s", (claims.user_id,)).fetchone()
        if user is None:
            raise DomainError(401, "UNAUTHENTICATED", "Account no longer exists.")
        scope = None if is_super(claims) else claims.tenant_id
        tenant = conn.execute("SELECT tenant_id, name, branding FROM tenants WHERE tenant_id=%s",
                              (user["tenant_id"],)).fetchone() if user["tenant_id"] else None
        leagues = conn.execute(
            "SELECT league_id, tenant_id, name, sport_id FROM ref_leagues WHERE (%s::text IS NULL OR tenant_id=%s)"
            " ORDER BY league_id", (scope, scope)).fetchall()
        clubs = conn.execute(
            "SELECT club_id, tenant_id, name FROM ref_clubs WHERE (%s::text IS NULL OR tenant_id=%s)"
            " ORDER BY club_id", (scope, scope)).fetchall()
        products = store.list_products(conn, scope)
    return {"user": _user_json(user), "tenant": tenant, "leagues": leagues, "clubs": clubs,
            "products": products, "capabilities": _capabilities(claims)}


def _capabilities(c: Claims) -> dict:
    return {"can_score": c.role in ("super_admin", "league_organizer"),
            "can_manage_roster": c.role in ("super_admin", "club_manager"),
            "can_buy": True}


# ------------------------------------------------------------------------------ clubs --------
@router.get("/clubs/{club_id}")
def club_profile(club_id: str, request: Request):
    claims = authenticate(request)
    with tx() as conn:
        club = conn.execute("SELECT * FROM ref_clubs WHERE club_id=%s", (club_id,)).fetchone()
        if club is None:
            raise DomainError(404, "CLUB_NOT_FOUND", f"Club {club_id} does not exist.", {"club_id": club_id})
        if not is_super(claims) and claims.tenant_id != club["tenant_id"]:
            raise forbidden()
        players = conn.execute(
            "SELECT player_id, name FROM ref_players WHERE club_id=%s ORDER BY player_id", (club_id,)).fetchall()
    return {**club, "roster": players}


# ----------------------------------------------------------------------------- store --------
@router.get("/products")
def products(request: Request):
    claims = authenticate(request)
    with tx() as conn:
        return {"products": store.list_products(conn, None if is_super(claims) else claims.tenant_id)}


def _check_variant_tenants(conn, claims: Claims, variant_ids: list[str]) -> None:
    if is_super(claims):
        return
    rows = conn.execute(
        "SELECT p.tenant_id FROM variants v JOIN products p ON p.product_id=v.product_id"
        " WHERE v.variant_id = ANY(%s)", (variant_ids,)).fetchall()
    if any(r["tenant_id"] != claims.tenant_id for r in rows):
        raise forbidden("This product belongs to another tenant.")


@router.post("/checkout")
async def checkout(request: Request):
    claims = authenticate(request)
    body = await read_json_object(request)
    if body.get("customer_id") is None:
        body = {**body, "customer_id": claims.user_id}

    def work(conn):
        items = body.get("items")
        if isinstance(items, list):
            ids = [i.get("variant_id") for i in items if isinstance(i, dict) and is_id(i.get("variant_id"))]
            if ids:
                _check_variant_tenants(conn, claims, ids)
        return store.checkout(conn, body)
    status, out = await run_tx(work)
    return JSONResponse(status_code=status, content=out)


def _order_scope(conn, claims: Claims, order_id: str, *, manage: bool) -> dict:
    row = conn.execute("SELECT order_id, customer_id FROM orders WHERE order_id=%s", (order_id,)).fetchone()
    if row is None:
        raise DomainError(404, "ORDER_NOT_FOUND", f"Order {order_id} does not exist.", {"order_id": order_id})
    if is_super(claims):
        return row
    tenant = conn.execute(
        "SELECT DISTINCT p.tenant_id, p.club_id FROM order_items oi JOIN variants v ON v.variant_id=oi.variant_id"
        " JOIN products p ON p.product_id=v.product_id WHERE oi.order_id=%s", (order_id,)).fetchall()
    in_tenant = all(t["tenant_id"] == claims.tenant_id for t in tenant)
    if not in_tenant:
        raise forbidden()
    if claims.role == "club_manager" and all(t["club_id"] == claims.club_id for t in tenant):
        return row
    if not manage and row["customer_id"] == claims.user_id:
        return row
    raise forbidden()


@router.get("/orders/{order_id}")
def get_order(order_id: str, request: Request):
    claims = authenticate(request)
    with tx() as conn:
        _order_scope(conn, claims, order_id, manage=False)
        return store.get_order(conn, order_id)


@router.post("/orders/{order_id}/status")
async def order_status(order_id: str, request: Request):
    claims = authenticate(request)
    body = await read_json_object(request)
    new_status = body.get("status")
    if not isinstance(new_status, str):
        raise validation_error(["status"])

    def work(conn):
        _order_scope(conn, claims, order_id, manage=True)
        return store.transition_order(conn, order_id, new_status)
    return await run_tx(work)


@router.post("/matches/{match_id}/pin")
async def pin_product(match_id: str, request: Request):
    """Pin a product to a match page; connected clients are notified after the commit."""
    claims = authenticate(request)
    body = await read_json_object(request)
    f = Fields()
    product_id = f.need_id(body, "product_id")
    f.check()
    if claims.role not in ("super_admin", "league_organizer", "club_manager"):
        raise forbidden()

    def work(conn):
        p = conn.execute("SELECT * FROM products WHERE product_id=%s", (product_id,)).fetchone()
        if p is None:
            raise DomainError(404, "PRODUCT_NOT_FOUND", f"Product {product_id} does not exist.",
                              {"product_id": product_id})
        if not is_super(claims):
            if p["tenant_id"] != claims.tenant_id or (claims.role == "club_manager" and p["club_id"] != claims.club_id):
                raise forbidden()
        conn.execute("UPDATE products SET pinned_match_id=NULL WHERE pinned_match_id=%s", (match_id,))
        conn.execute("UPDATE products SET pinned_match_id=%s WHERE product_id=%s", (match_id, product_id))
        return {"match_id": match_id, "product_id": product_id, "name": p["name"]}
    out = await run_tx(work)
    await realtime.hub.publish(match_id, {"type": "product_pinned", **out})
    return out


@router.get("/matches/{match_id}/pinned")
def pinned_product(match_id: str, request: Request):
    claims = authenticate(request)
    with tx() as conn:
        prods = [p for p in store.list_products(conn, None if is_super(claims) else claims.tenant_id)
                 if p["pinned_match_id"] == match_id]
    return {"match_id": match_id, "product": prods[0] if prods else None}


# --------------------------------------------------------------------------- roster ---------
def _authorize_roster_body(conn, claims: Claims, body: dict) -> None:
    """Super admin anywhere; a club manager only for moves leaving their own club's squad."""
    if is_super(claims):
        return
    if claims.role != "club_manager":
        raise forbidden()
    sid = body.get("from_squad_id")
    if not is_id(sid):
        return  # schema error is reported by the domain (400)
    sq = conn.execute("SELECT club_id, tenant_id FROM roster_squads WHERE squad_id=%s", (sid,)).fetchone()
    if sq is None:
        return  # nonexistent -> domain answers 404
    if sq["club_id"] != claims.club_id or sq["tenant_id"] != claims.tenant_id:
        raise forbidden()


@router.post("/roster/transfer")
async def roster_transfer(request: Request):
    claims = authenticate(request)
    body = await read_json_object(request)
    if claims.role not in ("super_admin", "club_manager"):
        raise forbidden()
    if body.get("requested_by") is None:
        body = {**body, "requested_by": claims.user_id}

    def work(conn):
        _authorize_roster_body(conn, claims, body)
        return roster.transfer(conn, body)
    status, out = await run_tx(work)
    return JSONResponse(status_code=status, content=out)


@router.get("/roster/history/{player_id}")
def roster_history(player_id: str, request: Request, as_of: str | None = None):
    claims = authenticate(request)
    with tx() as conn:
        row = conn.execute("SELECT rp.league_id, rs.club_id, rs.tenant_id FROM roster_players rp"
                           " LEFT JOIN roster_squads rs ON rs.squad_id=rp.initial_squad_id"
                           " WHERE rp.player_id=%s", (player_id,)).fetchone()
        if row is not None and not is_super(claims) and (row["tenant_id"] != claims.tenant_id):
            raise forbidden()
        return roster.history(conn, player_id, as_of)


# ------------------------------------------------------------------------- offline sync ------
@router.post("/offline-sync")
async def offline_sync(request: Request):
    claims = authenticate(request)
    body = await read_json_object(request)

    def work(conn):
        def authorize(action: dict) -> None:
            if action["type"] == "roster_transfer":
                _authorize_roster_body(conn, claims, action["payload"])
                return
            if is_super(claims):
                return
            if claims.role != "league_organizer":
                raise forbidden()
            payload = action["payload"]
            league_id = None
            lookup = getattr(ports.scoring(), "match_league_id", None)
            if callable(lookup) and is_id(payload.get("match_id")):
                league_id = lookup(conn, payload["match_id"])
            if league_id is None and isinstance(payload.get("payload"), dict):
                league_id = payload["payload"].get("league_id")
            if league_id != claims.league_id:
                raise forbidden()
        return offline.sync(conn, body, authorize=authorize)
    return await run_tx(work)
