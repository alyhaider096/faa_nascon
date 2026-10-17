"""Store: concurrency, atomic multi-item reservation, mock gateway, replay, receipts (Section 5.12)."""
import base64
import io
import os
import re
import threading
import time

import httpx
import psycopg
import pypdf
import pytest

from app.core.signing import sign_record

M, L = "var-jersey-001-M", "var-jersey-001-L"


def body(order_id="ord-001", items=None, discount=None, token="tok_success", customer="cust-001"):
    return {"order_id": order_id, "customer_id": customer,
            "items": items if items is not None else [{"variant_id": M, "quantity": 1}],
            "discount_code": discount, "payment": {"token": token}}


def buy(client, **kw):
    return client.post("/audit/v1/checkout", json=body(**kw))


def inv(client, vid=M):
    r = client.get(f"/audit/v1/inventory/{vid}")
    assert r.status_code == 200
    return r.json()


def pdf_text(b64: str) -> str:
    raw = base64.b64decode(b64)
    assert raw.startswith(b"%PDF")
    return "\n".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(raw)).pages)


def db():
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)


# ----------------------------------------------------------------------- happy path ---------
def test_success_response_shape_receipt_signature_and_pdf(client, reset):
    r = buy(client)
    assert r.status_code == 201
    b = r.json()
    assert b["order_id"] == "ord-001" and b["status"] == "paid" and b["currency"] == "PKR"
    assert b["items"] == [{"variant_id": M, "quantity": 1, "unit_price_minor": 450000}]
    assert (b["subtotal_minor"], b["discount_minor"], b["total_minor"]) == (450000, 0, 450000)
    assert b["payment"] == {"authorization_id": "auth_1", "capture_id": "cap_1", "state": "captured"}
    rec = b["receipt"]
    p = rec["payload"]
    assert set(p) == {"order_id", "customer_id", "items", "subtotal_minor", "discount_minor",
                      "total_minor", "currency", "paid_at"}
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", p["paid_at"])
    assert rec["signature"] == sign_record("ord-001", p, salt="demo-salt")
    assert len(rec["signature"]) == 64 and rec["signature"] == rec["signature"].lower()
    text = pdf_text(rec["pdf_base64"])
    assert "ord-001" in text and "PKR 4500.00" in text
    assert inv(client) == {"variant_id": M, "stock": 0, "reserved": 0}


def test_discount_floor_and_dynamic_pdf_total(client, reset):
    r = buy(client, items=[{"variant_id": L, "quantity": 3}], discount="WELCOME10")
    b = r.json()
    assert r.status_code == 201
    assert (b["subtotal_minor"], b["discount_minor"], b["total_minor"]) == (1350000, 135000, 1215000)
    text = pdf_text(b["receipt"]["pdf_base64"])
    assert "PKR 12150.00" in text and "PKR 4500.00" in text          # unit price line also present
    assert "PKR 4,5" not in text                                      # no thousands separators
    assert b["receipt"]["payload"]["total_minor"] == 1215000


def test_discount_is_floored(client, reset):
    with db() as c:
        c.execute("UPDATE variants SET price_minor=12345 WHERE variant_id=%s", (L,))
    b = buy(client, items=[{"variant_id": L, "quantity": 1}], discount="WELCOME10").json()
    assert (b["subtotal_minor"], b["discount_minor"], b["total_minor"]) == (12345, 1234, 11111)
    assert "PKR 111.11" in pdf_text(b["receipt"]["pdf_base64"])


def test_scheduled_price_change_applies_only_when_effective(client, reset):
    with db() as c:
        c.execute("INSERT INTO price_schedule (variant_id, effective_at, price_minor)"
                  " VALUES (%s, now() - interval '1 hour', 500000)", (L,))
        c.execute("INSERT INTO price_schedule (variant_id, effective_at, price_minor)"
                  " VALUES (%s, now() + interval '1 day', 999999)", (L,))
    b = buy(client, items=[{"variant_id": L, "quantity": 1}]).json()
    assert b["items"][0]["unit_price_minor"] == 500000 and b["total_minor"] == 500000


def test_multi_item_order_totals(client, reset):
    b = buy(client, items=[{"variant_id": M, "quantity": 1}, {"variant_id": L, "quantity": 2}]).json()
    assert b["subtotal_minor"] == 1350000
    assert [i["variant_id"] for i in b["items"]] == [M, L]               # request order preserved
    assert inv(client, M)["stock"] == 0 and inv(client, L)["stock"] == 3


def test_reset_stock_override(client, reset):
    out = reset({"stock": {M: 7}})
    assert out["stock"] == {M: 7, L: 5}
    assert inv(client, M)["stock"] == 7


# ---------------------------------------------------------------------- validation order -----
@pytest.mark.parametrize("mutate,field", [
    (lambda b: b.update(items=[]), "items"),
    (lambda b: b.update(items=[{"variant_id": M, "quantity": 1}] * 2), "items"),
    (lambda b: b.update(items=[{"variant_id": f"v{i}", "quantity": 1} for i in range(11)]), "items"),
    (lambda b: b.update(items=[{"variant_id": M, "quantity": 0}]), "quantity"),
    (lambda b: b.update(items=[{"variant_id": M, "quantity": 11}]), "quantity"),
    (lambda b: b.update(items=[{"variant_id": M, "quantity": True}]), "quantity"),
    (lambda b: b.update(items=[{"variant_id": M, "quantity": 1.0}]), "quantity"),
    (lambda b: b.update(items=[{"variant_id": M, "quantity": "1"}]), "quantity"),
    (lambda b: b.update(items="nope"), "items"),
    (lambda b: b.update(items=[{"variant_id": 5, "quantity": 1}]), "variant_id"),
    (lambda b: b.pop("payment"), "payment"),
    (lambda b: b.update(payment={"token": 5}), "payment"),
    (lambda b: b.update(order_id="bad id!"), "order_id"),
    (lambda b: b.pop("order_id"), "order_id"),
    (lambda b: b.update(customer_id=""), "customer_id"),
    (lambda b: b.update(customer_id=7), "customer_id"),
    (lambda b: b.update(discount_code=5), "discount_code"),
])
def test_schema_errors_are_400_with_fields(client, reset, mutate, field):
    b = body()
    mutate(b)
    r = client.post("/audit/v1/checkout", json=b)
    assert r.status_code == 400, r.text
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR" and field in err["details"]["fields"]
    assert inv(client)["stock"] == 1


def test_error_precedence_400_then_404_then_discount_then_409(client, reset):
    r = buy(client, items=[{"variant_id": "var-nope", "quantity": 1}], discount="BOGUS")
    assert r.status_code == 404 and r.json()["error"]["code"] == "VARIANT_NOT_FOUND"
    assert r.json()["error"]["details"]["variant_id"] == "var-nope"
    r = buy(client, items=[{"variant_id": M, "quantity": 5}], discount="BOGUS")
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_DISCOUNT_CODE"
    r = buy(client, items=[{"variant_id": M, "quantity": 5}], discount="WELCOME10", token="tok_declined")
    assert r.status_code == 409 and r.json()["error"]["code"] == "OUT_OF_STOCK"
    # a bad schema beats a missing variant
    r = buy(client, items=[{"variant_id": "var-nope", "quantity": 0}])
    assert r.status_code == 400
    assert buy(client, discount="welcome10").status_code == 400          # codes are case-sensitive


def test_out_of_stock_error_body(client, reset):
    assert buy(client).status_code == 201
    r = buy(client, order_id="ord-002")
    assert r.status_code == 409
    e = r.json()["error"]
    assert e["code"] == "OUT_OF_STOCK" and e["details"] == {"variant_id": M} and isinstance(e["message"], str)


# --------------------------------------------------------------- atomic multi-item rollback ---
def test_multi_item_failure_reserves_nothing(client, reset):
    r = buy(client, items=[{"variant_id": L, "quantity": 2}, {"variant_id": M, "quantity": 5}])
    assert r.status_code == 409 and r.json()["error"]["details"]["variant_id"] == M
    assert inv(client, L) == {"variant_id": L, "stock": 5, "reserved": 0}
    assert inv(client, M) == {"variant_id": M, "stock": 1, "reserved": 0}
    # the first failing item in request order is reported
    r = buy(client, items=[{"variant_id": M, "quantity": 5}, {"variant_id": L, "quantity": 9}])
    assert r.json()["error"]["details"]["variant_id"] == M


# ---------------------------------------------------------------------- payment failures -----
def test_declined_releases_and_allows_later_purchase(client, reset):
    r = buy(client, token="tok_declined")
    assert r.status_code == 402 and r.json()["error"]["code"] == "PAYMENT_DECLINED"
    assert inv(client) == {"variant_id": M, "stock": 1, "reserved": 0}
    assert buy(client, order_id="ord-retry").status_code == 201
    assert inv(client)["stock"] == 0


def test_capture_failure_voids_and_releases(client, reset):
    r = buy(client, token="tok_capture_fail")
    assert r.status_code == 402 and r.json()["error"]["code"] == "PAYMENT_CAPTURE_FAILED"
    assert inv(client) == {"variant_id": M, "stock": 1, "reserved": 0}
    ok = buy(client, order_id="ord-after")
    assert ok.status_code == 201 and ok.json()["payment"]["authorization_id"] == "auth_1"   # no id burned


def test_unknown_token_is_declined(client, reset):
    r = buy(client, token="tok_whatever")
    assert r.status_code == 402 and inv(client)["stock"] == 1


# ---------------------------------------------------------------------------- idempotency ----
def test_replay_returns_identical_stored_result_without_second_reservation(client, reset):
    first = buy(client)
    time.sleep(1.1)                       # a recomputed paid_at would differ by now
    again = buy(client)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json() == first.json()
    assert again.json()["receipt"]["payload"]["paid_at"] == first.json()["receipt"]["payload"]["paid_at"]
    assert inv(client)["stock"] == 0


def test_replay_wins_even_after_stock_is_gone_and_changed_body_conflicts(client, reset):
    first = buy(client)
    assert buy(client, order_id="other").status_code == 409                 # out of stock for others
    assert buy(client).status_code == 200                                    # replay still 200
    r = buy(client, customer="someone-else")
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_ORDER_ID"
    r = buy(client, items=[{"variant_id": L, "quantity": 1}])
    assert r.status_code == 409 and r.json()["error"]["code"] == "DUPLICATE_ORDER_ID"
    assert first.json()["order_id"] == "ord-001"


def test_failed_attempt_is_not_stored_so_same_id_can_retry(client, reset):
    assert buy(client, token="tok_declined").status_code == 402
    assert buy(client, token="tok_success").status_code == 201


# ---------------------------------------------------------------------------- concurrency ----
def run_parallel(server, n, make_body):
    results = [None] * n
    barrier = threading.Barrier(n)

    def worker(i):
        with httpx.Client(base_url=server, timeout=30) as c:
            barrier.wait()
            results[i] = c.post("/audit/v1/checkout", json=make_body(i))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    t0 = time.time()
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results, time.time() - t0


def test_twenty_buyers_last_unit_exactly_one_wins(client, server, reset):
    results, elapsed = run_parallel(server, 20, lambda i: body(order_id=f"burst-{i}", customer=f"c{i}"))
    codes = sorted(r.status_code for r in results)
    assert codes == [201] + [409] * 19
    assert all(r.json()["error"]["code"] == "OUT_OF_STOCK" for r in results if r.status_code == 409)
    assert elapsed < 10
    assert inv(client) == {"variant_id": M, "stock": 0, "reserved": 0}


def test_burst_never_oversells_larger_stock(client, server, reset):
    reset({"stock": {L: 5}})
    results, _ = run_parallel(server, 20, lambda i: body(order_id=f"l-{i}", items=[{"variant_id": L, "quantity": 1}]))
    ok = [r for r in results if r.status_code == 201]
    assert len(ok) == 5 and sorted(r.status_code for r in results) == [201] * 5 + [409] * 15
    assert inv(client, L) == {"variant_id": L, "stock": 0, "reserved": 0}
    auths = {r.json()["payment"]["authorization_id"] for r in ok}
    assert len(auths) == 5


def test_mixed_failures_in_burst_release_stock(client, server, reset):
    reset({"stock": {M: 3, L: 5}})
    tokens = ["tok_success", "tok_declined", "tok_capture_fail"]
    results, _ = run_parallel(server, 18, lambda i: body(order_id=f"mx-{i}", token=tokens[i % 3],
                                                         items=[{"variant_id": M, "quantity": 1}]))
    codes = [r.status_code for r in results]
    assert codes.count(201) <= 3 and codes.count(201) >= 1
    assert set(codes) <= {201, 402, 409}
    sold = codes.count(201)
    assert inv(client, M) == {"variant_id": M, "stock": 3 - sold, "reserved": 0}


def test_concurrent_identical_order_ids_apply_once(client, server, reset):
    reset({"stock": {M: 5}})
    results, _ = run_parallel(server, 10, lambda i: body(order_id="same-order", items=[{"variant_id": M, "quantity": 2}]))
    assert sorted(r.status_code for r in results) == [200] * 9 + [201]
    import json
    assert len({json.dumps(r.json(), sort_keys=True) for r in results}) == 1
    assert inv(client, M)["stock"] == 3


def test_opposite_item_orders_do_not_deadlock(client, server, reset):
    reset({"stock": {M: 50, L: 50}})
    pair = [{"variant_id": M, "quantity": 1}, {"variant_id": L, "quantity": 1}]
    results, elapsed = run_parallel(
        server, 20, lambda i: body(order_id=f"dl-{i}", items=pair if i % 2 else list(reversed(pair))))
    assert all(r.status_code == 201 for r in results) and elapsed < 10
    assert inv(client, M)["stock"] == 30 and inv(client, L)["stock"] == 30


def test_inventory_unknown_variant_404(client, reset):
    r = client.get("/audit/v1/inventory/var-nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "VARIANT_NOT_FOUND"
    assert set(inv(client)) == {"variant_id", "stock", "reserved"}


def test_reset_restores_stock_and_orders(client, reset):
    assert buy(client).status_code == 201
    reset()
    assert inv(client)["stock"] == 1
    assert buy(client).status_code == 201                     # same order_id usable after reset
    assert buy(client, order_id="ord-x").status_code == 409
