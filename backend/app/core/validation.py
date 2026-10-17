"""Strict request validation helpers. Everything here yields 400 VALIDATION_ERROR (never 422)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

from starlette.requests import Request

from .errors import DomainError, validation_error

ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name}")


def parse_json_bytes(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise DomainError(400, "VALIDATION_ERROR", "Request body is not valid JSON.", {"fields": []})


async def read_json_object(request: Request, *, required: bool = True) -> dict:
    """Read the body as a JSON object. Empty body is {} only when not required."""
    raw = await request.body()
    if not raw.strip():
        if required:
            raise DomainError(400, "VALIDATION_ERROR", "A JSON object body is required.", {"fields": []})
        return {}
    body = parse_json_bytes(raw)
    if not isinstance(body, dict):
        raise DomainError(400, "VALIDATION_ERROR", "Request body must be a JSON object.", {"fields": []})
    return body


def is_int(v: Any) -> bool:
    return type(v) is int  # excludes bool


def is_id(v: Any) -> bool:
    return isinstance(v, str) and ID_RE.fullmatch(v) is not None


def parse_date(v: Any) -> date | None:
    if not isinstance(v, str) or not DATE_RE.fullmatch(v):
        return None
    try:
        return date(int(v[0:4]), int(v[5:7]), int(v[8:10]))
    except ValueError:
        return None


def parse_ts(v: Any) -> datetime | None:
    if not isinstance(v, str) or not TS_RE.fullmatch(v):
        return None
    try:
        return datetime(int(v[0:4]), int(v[5:7]), int(v[8:10]), int(v[11:13]), int(v[14:16]),
                        int(v[17:19]), tzinfo=timezone.utc)
    except ValueError:
        return None


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Fields:
    """Collects offending field names, then raises a single VALIDATION_ERROR."""

    def __init__(self) -> None:
        self.bad: list[str] = []

    def add(self, name: str) -> None:
        if name not in self.bad:
            self.bad.append(name)

    def need_id(self, obj: dict, key: str, prefix: str = "") -> str | None:
        v = obj.get(key)
        if not is_id(v):
            self.add(prefix + key)
            return None
        return v

    def opt_id(self, obj: dict, key: str, prefix: str = "") -> str | None:
        v = obj.get(key)
        if v is None:
            return None
        if not is_id(v):
            self.add(prefix + key)
            return None
        return v

    def need_str(self, obj: dict, key: str, prefix: str = "", *, min_len: int = 1,
                 max_len: int = 200) -> str | None:
        v = obj.get(key)
        if not isinstance(v, str) or not (min_len <= len(v) <= max_len):
            self.add(prefix + key)
            return None
        return v

    def need_date(self, obj: dict, key: str, prefix: str = "") -> date | None:
        d = parse_date(obj.get(key))
        if d is None:
            self.add(prefix + key)
        return d

    def need_int(self, obj: dict, key: str, prefix: str = "", *, lo: int | None = None,
                 hi: int | None = None) -> int | None:
        v = obj.get(key)
        if not is_int(v) or (lo is not None and v < lo) or (hi is not None and v > hi):
            self.add(prefix + key)
            return None
        return v

    def check(self) -> None:
        if self.bad:
            raise validation_error(self.bad)
