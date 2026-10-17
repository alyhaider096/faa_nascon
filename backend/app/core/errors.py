"""Shared error policy: one DomainError, one JSON shape, 400 (never 422), no leaking 5xx details."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("nascon.errors")


class DomainError(Exception):
    """Carries the HTTP status, an exact Appendix B code and an object of details."""

    def __init__(self, status: int, code: str, message: str = "", details: dict | None = None,
                 headers: dict | None = None):
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code.replace("_", " ").capitalize()
        self.details = details or {}
        self.headers = headers or {}

    def body(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def validation_error(fields: list[str], message: str = "Request validation failed.") -> DomainError:
    return DomainError(400, "VALIDATION_ERROR", message, {"fields": list(fields)})


def error_response(err: DomainError) -> JSONResponse:
    return JSONResponse(status_code=err.status, content=err.body(), headers=err.headers or None)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        return error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        fields = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
        return error_response(validation_error(fields))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return error_response(DomainError(exc.status_code, code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error")
        return error_response(DomainError(500, "INTERNAL_ERROR", "Internal server error."))
