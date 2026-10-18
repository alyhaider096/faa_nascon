"""PDF rendering regressions; these checks require no running database."""
import io

from pypdf import PdfReader
from app.domain.store import render_receipt_pdf


def test_large_receipt_paginates_and_retains_every_item_and_total():
    payload = {
        "order_id": "ord-layout-check", "customer_id": "customer-layout",
        "paid_at": "2026-10-18T08:00:00Z",
        "items": [{"variant_id": f"var-layout-{index:03}", "quantity": 1,
                   "unit_price_minor": 250000} for index in range(50)],
        "subtotal_minor": 12500000, "discount_minor": 1250000,
        "total_minor": 11250000,
    }
    reader = PdfReader(io.BytesIO(render_receipt_pdf(payload)))
    assert len(reader.pages) > 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    for item in payload["items"]:
        assert item["variant_id"] in text
    assert "PKR 112500.00" in text
    assert "Total" in reader.pages[-1].extract_text()
    assert all("ITEM / VARIANT" in page.extract_text() for page in reader.pages)
