"""Merchandise store: catalogue, concurrency-safe checkout, mock gateway, receipts (Section 5.12).

Checkout is ONE database transaction (the caller's connection):
  validate -> replay check (per-order advisory lock) -> variants exist -> discount ->
  lock variant rows in sorted order -> check stock -> reserve -> mock gateway ->
  commit reservation + order + receipt + outbox event.
Any exception (out of stock, declined, capture failed) rolls the whole transaction back, which is
exactly "reserve nothing / release the reservation": there is no partial state to clean up.
"""
from __future__ import annotations

import base64
import io
import re
from typing import Any

from psycopg.types.json import Jsonb
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from ..core.errors import DomainError
from ..core.signing import request_hash, sign_record
from ..core.validation import Fields, is_id, is_int, utc_now_str

DISCOUNT_FLOOR_DIV = 100
GATEWAY_OK, GATEWAY_DECLINED, GATEWAY_CAPTURE_FAIL = "tok_success", "tok_declined", "tok_capture_fail"

ORDER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending": ("paid", "cancelled"),
    "paid": ("packed", "cancelled", "refunded"),
    "packed": ("shipped", "refunded"),
    "shipped": ("delivered", "refunded"),
    "delivered": ("refunded",),
    "cancelled": (),
    "refunded": (),
}


# ---------------------------------------------------------------------- validation ----------
def _validate_checkout(body: dict) -> dict:
    f = Fields()
    out: dict[str, Any] = {}
    out["order_id"] = f.need_id(body, "order_id")
    cust = body.get("customer_id")
    if not isinstance(cust, str) or not (1 <= len(cust) <= 200):
        f.add("customer_id")
        cust = None
    out["customer_id"] = cust

    items = body.get("items")
    parsed: list[dict] = []
    if not isinstance(items, list) or not (1 <= len(items) <= 10):
        f.add("items")
    else:
        seen: set[str] = set()
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                f.add(f"items[{i}]")
                f.add("items")
                continue
            vid = it.get("variant_id")
            if not is_id(vid):
                f.add(f"items[{i}].variant_id")
                f.add("variant_id")
            elif vid in seen:
                f.add(f"items[{i}].variant_id")
                f.add("items")
            else:
                seen.add(vid)
            q = it.get("quantity")
            if not is_int(q) or not (1 <= q <= 10):
                f.add(f"items[{i}].quantity")
                f.add("quantity")
            if is_id(vid) and is_int(q):
                parsed.append({"variant_id": vid, "quantity": q})
    out["items"] = parsed

    code = body.get("discount_code")
    if code is not None and (not isinstance(code, str) or not (1 <= len(code) <= 64)):
        f.add("discount_code")
        code = None
    out["discount_code"] = code

    pay = body.get("payment")
    token = None
    if not isinstance(pay, dict) or not isinstance(pay.get("token"), str) or not pay["token"]:
        f.add("payment")
        f.add("payment.token")
    else:
        token = pay["token"]
    out["token"] = token
    f.check()
    out["_hash"] = request_hash({
        "order_id": out["order_id"], "customer_id": cust, "items": parsed,
        "discount_code": code, "payment": {"token": token},
    })
    return out


# --------------------------------------------------------------------------- pricing --------
def _fmt_major(minor: int) -> str:
    """4500.00 PKR -> '4500.00' (major units, two decimals, no thousands separator)."""
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    return f"{sign}{minor // 100}.{minor % 100:02d}"


def _current_prices(conn, variant_ids: list[str]) -> dict[str, int]:
    rows = conn.execute(
        "SELECT v.variant_id, COALESCE(("
        "  SELECT ps.price_minor FROM price_schedule ps WHERE ps.variant_id=v.variant_id"
        "  AND ps.effective_at <= now() ORDER BY ps.effective_at DESC, ps.id DESC LIMIT 1"
        "), v.price_minor) AS price FROM variants v WHERE v.variant_id = ANY(%s)", (variant_ids,),
    ).fetchall()
    return {r["variant_id"]: int(r["price"]) for r in rows}


# ----------------------------------------------------------------------- mock gateway -------
def _gateway(token: str) -> None:
    """Team-owned mock payment gateway. Raises the exact 402s; never touches the network."""
    if token == GATEWAY_OK:
        return
    if token == GATEWAY_CAPTURE_FAIL:
        # authorization succeeded, capture failed -> the authorization is voided by the caller
        raise DomainError(402, "PAYMENT_CAPTURE_FAILED", "Payment capture failed; authorization voided.")
    raise DomainError(402, "PAYMENT_DECLINED", "Payment was declined.")


# ------------------------------------------------------------------------------ PDF ---------
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


def _pdf_text(value: str, limit: int = 90) -> str:
    """Receipt text is drawn as plain glyphs (no markup engine), so HTML/quotes are inert."""
    value = _CTRL.sub(" ", value).encode("latin-1", "replace").decode("latin-1")
    return value if len(value) <= limit else value[: limit - 1] + "..."


def render_receipt_pdf(payload: dict, *, status: str = "PAID") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReceiptMeta", fontName="Helvetica", fontSize=10,
                              leading=15, textColor=colors.HexColor("#344155")))
    styles.add(ParagraphStyle(name="ReceiptHeading", fontName="Helvetica-Bold", fontSize=24,
                              leading=30, textColor=colors.HexColor("#142031")))
    def paragraph(value):
        return Paragraph(escape(_pdf_text(str(value), 240)), styles["ReceiptMeta"])

    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=48, leftMargin=48,
                            topMargin=48, bottomMargin=54,
                            title="Receipt " + _pdf_text(payload["order_id"], 40))
    story = [Paragraph("LEAGUEOPS", styles["ReceiptMeta"]), Spacer(1, 8),
             Paragraph("Payment Receipt", styles["ReceiptHeading"]), Spacer(1, 16)]
    meta = Table([[paragraph("Order"), paragraph(payload["order_id"])],
                  [paragraph("Customer"), paragraph(payload["customer_id"])],
                  [paragraph("Paid at"), paragraph(payload["paid_at"])],
                  [paragraph("Status"), paragraph(status)]], colWidths=[85, A4[0]-181])
    meta.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"),
                              ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
    story += [meta, Spacer(1, 24)]
    rows = [["ITEM / VARIANT", "QTY", "UNIT PRICE", "AMOUNT"]]
    for item in payload["items"]:
        rows.append([paragraph(item["variant_id"]), str(item["quantity"]),
                     "PKR " + _fmt_major(item["unit_price_minor"]),
                     "PKR " + _fmt_major(item["unit_price_minor"] * item["quantity"])])
    table = Table(rows, colWidths=[A4[0]-335, 35, 100, 104], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#142031")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (1,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (1,0), (-1,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 11),
        ("BOTTOMPADDING", (0,0), (-1,-1), 11),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#F0F4F8"), colors.white]),
        ("LINEBELOW", (0,0), (-1,0), 1, colors.HexColor("#40516A")),
    ]))
    totals = Table([["Subtotal", "PKR " + _fmt_major(payload["subtotal_minor"])],
                    ["Discount", "PKR " + _fmt_major(payload["discount_minor"])],
                    ["Total", "PKR " + _fmt_major(payload["total_minor"])]],
                   colWidths=[120,160], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"), ("FONTSIZE", (0,0), (-1,-1), 11),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 9), ("BOTTOMPADDING", (0,0), (-1,-1), 9),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#142031")),
        ("TEXTCOLOR", (0,-1), (-1,-1), colors.white),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
    ]))
    story += [table, Spacer(1,18), totals]
    def footer(page_canvas, document):
        page_canvas.saveState()
        page_canvas.setFont("Helvetica", 8)
        page_canvas.setFillColor(colors.HexColor("#526176"))
        page_canvas.drawString(48, 30, "LeagueOps | " + _pdf_text(payload["order_id"], 50))
        page_canvas.drawRightString(A4[0]-48, 30, "Page " + str(document.page))
        page_canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


# ------------------------------------------------------------------------- checkout --------
def checkout(conn, body: dict) -> tuple[int, dict]:
    v = _validate_checkout(body)                                              # 400
    order_id = v["order_id"]

    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("ord:" + order_id,))
    prior = conn.execute("SELECT request_hash, response FROM orders WHERE order_id=%s",
                         (order_id,)).fetchone()
    if prior is not None:                         # replay judged before stock/payment state
        if prior["request_hash"] == v["_hash"]:
            return 200, prior["response"]
        raise DomainError(409, "DUPLICATE_ORDER_ID",
                          f"order_id {order_id} was already used with a different request.",
                          {"order_id": order_id})

    wanted = [it["variant_id"] for it in v["items"]]
    prices = _current_prices(conn, wanted)
    for vid in wanted:                                                         # 404
        if vid not in prices:
            raise DomainError(404, "VARIANT_NOT_FOUND", f"Variant {vid} does not exist.",
                              {"variant_id": vid})

    percent = 0
    if v["discount_code"] is not None:                                         # 400
        dc = conn.execute("SELECT percent FROM discount_codes WHERE code=%s AND active",
                          (v["discount_code"],)).fetchone()
        if dc is None:
            raise DomainError(400, "INVALID_DISCOUNT_CODE", "Unknown discount code.",
                              {"discount_code": v["discount_code"]})
        percent = dc["percent"]

    # Lock all variant rows in one stable (sorted) order => no deadlocks between buyers.
    stock = {r["variant_id"]: r for r in conn.execute(
        "SELECT variant_id, stock FROM variants WHERE variant_id = ANY(%s) ORDER BY variant_id FOR UPDATE",
        (sorted(wanted),)).fetchall()}
    for it in v["items"]:                                                      # 409, nothing reserved
        if stock[it["variant_id"]]["stock"] < it["quantity"]:
            raise DomainError(409, "OUT_OF_STOCK", f"Variant {it['variant_id']} has no stock left.",
                              {"variant_id": it["variant_id"]})
    for it in sorted(v["items"], key=lambda x: x["variant_id"]):               # reserve atomically
        n = conn.execute(
            "UPDATE variants SET stock=stock-%s, reserved=reserved+%s WHERE variant_id=%s AND stock>=%s",
            (it["quantity"], it["quantity"], it["variant_id"], it["quantity"])).rowcount
        if n != 1:  # cannot happen while rows are locked; fail closed rather than oversell
            raise DomainError(409, "OUT_OF_STOCK", f"Variant {it['variant_id']} has no stock left.",
                              {"variant_id": it["variant_id"]})

    _gateway(v["token"])      # 402 raises -> transaction rolls back -> reservation released

    for it in v["items"]:                                                      # commit reservation
        conn.execute("UPDATE variants SET reserved=reserved-%s WHERE variant_id=%s",
                     (it["quantity"], it["variant_id"]))

    items = [{"variant_id": it["variant_id"], "quantity": it["quantity"],
              "unit_price_minor": prices[it["variant_id"]]} for it in v["items"]]
    subtotal = sum(i["quantity"] * i["unit_price_minor"] for i in items)
    discount = subtotal * percent // DISCOUNT_FLOOR_DIV
    total = subtotal - discount
    n = conn.execute("SELECT nextval('payment_seq') AS n").fetchone()["n"]
    paid_at = utc_now_str()

    payload = {
        "order_id": order_id, "customer_id": v["customer_id"], "items": items,
        "subtotal_minor": subtotal, "discount_minor": discount, "total_minor": total,
        "currency": "PKR", "paid_at": paid_at,
    }
    signature = sign_record(order_id, payload)       # signs exactly what is returned below
    pdf = render_receipt_pdf(payload)
    response = {
        "order_id": order_id, "status": "paid", "currency": "PKR", "items": items,
        "subtotal_minor": subtotal, "discount_minor": discount, "total_minor": total,
        "payment": {"authorization_id": f"auth_{n}", "capture_id": f"cap_{n}", "state": "captured"},
        "receipt": {"payload": payload, "signature": signature,
                    "pdf_base64": base64.b64encode(pdf).decode("ascii")},
    }
    conn.execute(
        "INSERT INTO orders (order_id, customer_id, request_hash, status, currency, subtotal_minor,"
        " discount_minor, total_minor, response, pdf) VALUES (%s,%s,%s,'paid','PKR',%s,%s,%s,%s,%s)",
        (order_id, v["customer_id"], v["_hash"], subtotal, discount, total, Jsonb(response), pdf))
    for i in items:
        conn.execute("INSERT INTO order_items (order_id, variant_id, quantity, unit_price_minor)"
                     " VALUES (%s,%s,%s,%s)", (order_id, i["variant_id"], i["quantity"], i["unit_price_minor"]))
    emit(conn, "order.status_changed", {"order_id": order_id, "from": None, "to": "paid"})
    return 201, response


def emit(conn, topic: str, payload: dict) -> None:
    """Transactional outbox: published to the queue by the worker only after this commits."""
    conn.execute("INSERT INTO outbox (topic, payload) VALUES (%s,%s)", (topic, Jsonb(payload)))


# ------------------------------------------------------------------------- reads -----------
def inventory(conn, variant_id: str) -> dict:
    row = conn.execute("SELECT variant_id, stock, reserved FROM variants WHERE variant_id=%s",
                       (variant_id,)).fetchone()
    if row is None:
        raise DomainError(404, "VARIANT_NOT_FOUND", f"Variant {variant_id} does not exist.",
                          {"variant_id": variant_id})
    return {"variant_id": row["variant_id"], "stock": row["stock"], "reserved": row["reserved"]}


def list_products(conn, tenant_id: str | None) -> list[dict]:
    """Catalogue for a tenant (None = every tenant, super admin)."""
    params: list = []
    where = "WHERE p.active"
    if tenant_id is not None:
        where += " AND p.tenant_id=%s"
        params.append(tenant_id)
    products = conn.execute(
        f"SELECT p.* FROM products p {where} ORDER BY p.product_id", params).fetchall()
    out = []
    for p in products:
        vids = [r["variant_id"] for r in conn.execute(
            "SELECT variant_id FROM variants WHERE product_id=%s ORDER BY variant_id", (p["product_id"],))]
        prices = _current_prices(conn, vids) if vids else {}
        variants = []
        for r in conn.execute("SELECT * FROM variants WHERE product_id=%s ORDER BY variant_id",
                              (p["product_id"],)).fetchall():
            variants.append({"variant_id": r["variant_id"], "attributes": r["attributes"],
                             "price_minor": prices[r["variant_id"]], "currency": r["currency"],
                             "stock": r["stock"]})
        out.append({"product_id": p["product_id"], "tenant_id": p["tenant_id"], "club_id": p["club_id"],
                    "name": p["name"], "category": p["category"], "description": p["description"],
                    "pinned_match_id": p["pinned_match_id"], "variants": variants})
    return out


def get_order(conn, order_id: str) -> dict:
    row = conn.execute("SELECT order_id, customer_id, status, response FROM orders WHERE order_id=%s",
                       (order_id,)).fetchone()
    if row is None:
        raise DomainError(404, "ORDER_NOT_FOUND", f"Order {order_id} does not exist.", {"order_id": order_id})
    resp = dict(row["response"])
    resp["status"] = row["status"]
    return resp


def transition_order(conn, order_id: str, new_status: str) -> dict:
    """Pending/Paid/Packed/Shipped/Delivered/Cancelled/Refunded state machine; each change is
    emitted to the internal queue. Cancelling or refunding a not-yet-shipped paid order returns
    its units to stock (refund simulation)."""
    if new_status not in ORDER_TRANSITIONS:
        raise DomainError(400, "VALIDATION_ERROR", "Unknown order status.", {"fields": ["status"]})
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("ord:" + order_id,))
    row = conn.execute("SELECT status FROM orders WHERE order_id=%s FOR UPDATE", (order_id,)).fetchone()
    if row is None:
        raise DomainError(404, "ORDER_NOT_FOUND", f"Order {order_id} does not exist.", {"order_id": order_id})
    old = row["status"]
    if new_status not in ORDER_TRANSITIONS[old]:
        raise DomainError(409, "ILLEGAL_TRANSITION", f"Cannot move order from {old} to {new_status}.",
                          {"from": old, "to": new_status})
    if new_status in ("cancelled", "refunded") and old in ("paid", "packed"):
        for it in conn.execute("SELECT variant_id, quantity FROM order_items WHERE order_id=%s ORDER BY variant_id",
                               (order_id,)).fetchall():
            conn.execute("UPDATE variants SET stock=stock+%s WHERE variant_id=%s", (it["quantity"], it["variant_id"]))
    conn.execute("UPDATE orders SET status=%s, updated_at=now() WHERE order_id=%s", (new_status, order_id))
    emit(conn, "order.status_changed", {"order_id": order_id, "from": old, "to": new_status})
    return {"order_id": order_id, "status": new_status, "previous_status": old}
