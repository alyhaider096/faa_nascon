"""Run the domain owner's SQLAlchemy services on the request's own psycopg transaction.

The scoring/standings/fixtures code takes a SQLAlchemy `Session`. Platform code owns one psycopg
connection per request (commit/rollback in `db.tx()`), so a Session is bound to that very
connection through a thin DBAPI proxy: SQLAlchemy never commits, rolls back or closes it, which
keeps offline sync, reset and the domain services in a single atomic transaction.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

import psycopg
from psycopg.adapt import AdaptersMap
from psycopg.rows import tuple_row
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

_local = threading.local()
_engine = None
_url: str | None = None


class _ConnProxy:
    """Presents a dict_row psycopg connection to SQLAlchemy without letting it end the transaction."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._c = conn

    def cursor(self, *args, **kwargs):
        kwargs.setdefault("row_factory", tuple_row)
        return self._c.cursor(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return self.cursor().execute(*args, **kwargs)

    def commit(self) -> None:       # the platform transaction owns commit
        return None

    def rollback(self) -> None:     # ... and rollback (savepoints are plain SQL)
        return None

    def close(self) -> None:
        return None

    @property
    def adapters(self):             # SQLAlchemy registers JSON loaders here; keep it off the real connection
        return AdaptersMap(self._c.adapters)

    def __getattr__(self, name):
        return getattr(self._c, name)


def _sqlalchemy_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+psycopg://", 1) if url.startswith("postgresql://") else url


def _creator():
    cur = getattr(_local, "conn", None)
    if cur is not None:
        return _ConnProxy(cur)
    return psycopg.connect(_url)        # only used for SQLAlchemy's own first-connect probe


def init(database_url: str) -> None:
    global _engine, _url
    _url = database_url
    _engine = create_engine(_sqlalchemy_url(database_url), creator=_creator, poolclass=NullPool, future=True)
    with _engine.connect():             # dialect initialisation on a throwaway connection
        pass


@contextmanager
def session(conn: psycopg.Connection):
    """A Session on `conn`. Nothing is committed here; close() does not end the transaction."""
    if _engine is None:
        from .config import get_settings
        init(get_settings().database_url)
    prev = getattr(_local, "conn", None)
    _local.conn = conn
    s = Session(bind=_engine, expire_on_commit=False, autoflush=True)
    try:
        yield s
        s.flush()
    finally:
        try:
            s.close()
        finally:
            _local.conn = prev
