"""Thin database layer over psycopg 3.

Everything the pipeline needs from Postgres goes through :class:`Database`, so
the loader stays easy to test and the SQL stays in one place.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

log = logging.getLogger(__name__)


class Database:
    def __init__(self, url: str):
        if not url:
            raise ValueError("DATABASE_URL is not set — copy .env.example to .env and fill it in")
        import psycopg  # imported lazily so parsing works without a DB driver

        self._psycopg = psycopg
        # prepare_threshold=None: no server-side prepared statements, so the
        # connection poolers (Neon / Supabase / PgBouncer) work in any mode
        self.conn = psycopg.connect(url, autocommit=True, prepare_threshold=None,
                                    application_name="pricetracker")

    # --------------------------------------------------------------- basics
    def execute(self, sql: str, params: dict[str, Any] | Sequence[Any] | None = None) -> int:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def query(self, sql: str, params: dict[str, Any] | Sequence[Any] | None = None) -> list[tuple]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []

    def copy_rows(self, table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
        n = 0
        cols = ", ".join(columns)
        with self.conn.cursor() as cur:
            with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as cp:
                for row in rows:
                    cp.write_row(row)
                    n += 1
        return n

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        with self.conn.transaction():
            yield self

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
