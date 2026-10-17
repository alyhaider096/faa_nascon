"""The one shared signing helper (Section 5.3 / Appendix A). Used by events and receipts.

signature = HMAC-SHA256(key=DAY1_SALT utf-8, message=id + "|" + canonical_json(payload))
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from .config import get_settings


def canonical(payload: Any) -> str:
    """Recursively sorted keys, no whitespace, literal Unicode, ints stay ints, no NaN."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def sign_record(record_id: str, payload: Any, *, salt: str | None = None) -> str:
    """Return the 64-char lowercase hex signature. `salt` may be injected for test vectors."""
    key = (salt if salt is not None else get_settings().day1_salt).encode("utf-8")
    message = (record_id + "|" + canonical(payload)).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def request_hash(body: Any) -> str:
    """Stable identity of a request body, used for idempotency comparisons (not a signature)."""
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
