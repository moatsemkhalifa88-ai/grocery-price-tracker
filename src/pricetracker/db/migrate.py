"""Apply sql/migrations/*.sql in order, once each."""

from __future__ import annotations

import logging
from pathlib import Path

from ..config import PROJECT_ROOT
from .connection import Database

log = logging.getLogger(__name__)
MIGRATIONS_DIR = PROJECT_ROOT / "sql" / "migrations"


def pending(db: Database, directory: Path = MIGRATIONS_DIR) -> list[Path]:
    # kept out of `public`, which some hosts (e.g. Supabase) expose through a REST API
    db.execute("CREATE SCHEMA IF NOT EXISTS ingest")
    db.execute(
        "CREATE TABLE IF NOT EXISTS ingest.schema_migrations ("
        " version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    done = {r[0] for r in db.query("SELECT version FROM ingest.schema_migrations")}
    return [p for p in sorted(directory.glob("*.sql")) if p.stem not in done]


def migrate(db: Database, directory: Path = MIGRATIONS_DIR) -> list[str]:
    applied = []
    for path in pending(db, directory):
        log.info("applying migration %s", path.name)
        with db.transaction():
            db.execute(path.read_text(encoding="utf-8"))
            db.execute("INSERT INTO ingest.schema_migrations (version) VALUES (%s)", (path.stem,))
        applied.append(path.stem)
    if not applied:
        log.info("database is up to date")
    return applied
