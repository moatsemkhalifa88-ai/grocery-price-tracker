"""Daily pipeline: extract → parse → load, one chain at a time.

For each enabled chain:
  1. download the latest Stores file and upsert branches
  2. choose which branches to track (config: cities / limit / explicit ids)
  3. for every tracked branch, take the newest PriceFull and PromoFull file,
     skip it if already processed, otherwise parse and load it
Every file's outcome is written to ingest.file_log, so a failed file never
blocks the rest and re-running the same day is safe (idempotent).
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import Settings, StoreSelection
from .db import loader
from .db.connection import Database
from .models import FileType, RemoteFile, StoreRecord
from .parsing.xml_parser import parse_prices, parse_promos, parse_stores
from .sources import CHAINS, Source, latest_per_store, make_source

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    loaded: int = 0
    skipped: int = 0
    failed: int = 0
    rows: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.failed and not self.loaded:
            return "failed"
        return "partial" if self.failed else "success"


# --------------------------------------------------------- store selection --

def select_stores(chain_key: str, stores: list[StoreRecord], sel: StoreSelection) -> list[int]:
    """Pick the branches to track for one chain."""
    forced = set(sel.include_store_ids.get(chain_key, []))

    def matches(s: StoreRecord) -> bool:
        if not sel.cities:
            return True
        hay = " ".join(x for x in (s.city, s.store_name, s.address) if x)
        return any(c in hay for c in sel.cities)

    candidates = sorted((s for s in stores if matches(s)), key=lambda s: s.store_id)
    chosen = [s.store_id for s in candidates if s.store_id not in forced]
    limit = max(sel.max_stores_per_chain - len(forced), 0)
    return sorted(forced | set(chosen[:limit]))


# --------------------------------------------------------------- raw files --

def save_raw(settings: Settings, f: RemoteFile, data: bytes) -> Path | None:
    if not settings.raw_keep:
        return None
    day = (f.meta.published_at or datetime.now()).strftime("%Y-%m-%d")
    path = settings.raw_dir / f.chain_key / day / f.name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def cleanup_raw(settings: Settings) -> int:
    """Delete raw day-folders older than the retention window."""
    cutoff = date.today() - timedelta(days=settings.raw_retention_days)
    removed = 0
    if not settings.raw_dir.exists():
        return 0
    for chain_dir in settings.raw_dir.iterdir():
        for day_dir in chain_dir.iterdir() if chain_dir.is_dir() else []:
            try:
                d = date.fromisoformat(day_dir.name)
            except ValueError:
                continue
            if d < cutoff:
                for p in day_dir.iterdir():
                    p.unlink()
                    removed += 1
                day_dir.rmdir()
    return removed


# ------------------------------------------------------------- processing --

def _process_file(db: Database, settings: Settings, src: Source, f: RemoteFile, stats: RunStats,
                  force: bool = False) -> None:
    if not force and loader.already_processed(db, f.name):
        stats.skipped += 1
        return

    t0 = time.monotonic()
    data: bytes = b""
    try:
        data = src.download(f)
        save_raw(settings, f, data)
        sha = hashlib.sha256(data).hexdigest()
        meta = f.meta
        store_id = meta.store_id

        if meta.file_type.is_price:
            snap = meta.published_at or datetime.now()
            newest = loader.latest_snapshot(db, meta.chain_id, store_id) if store_id is not None else None
            if newest is not None and snap <= newest:
                loader.log_file(db, f.name, meta, "skipped", sha256=sha, size_bytes=len(data),
                                error="older than the snapshot already loaded")
                stats.skipped += 1
                return
            records = list(parse_prices(data, meta))
            store_id = records[0].store_id if records else store_id
            res = loader.load_prices(db, records, chain_id=meta.chain_id, store_id=store_id,
                                     snapshot_at=snap, source_file=f.name,
                                     is_full=meta.file_type is FileType.PRICE_FULL)
            n = res["staged"]
            log.info("%s store %s: %d items, %d new rows (%d price changes, %d delisted)",
                     f.chain_key, store_id, n, res["inserted"], res["price_changes"], res["delisted"])
        elif meta.file_type.is_promo:
            promos = list(parse_promos(data, meta))
            store_id = promos[0].store_id if promos else store_id
            n = loader.load_promos(db, promos, chain_id=meta.chain_id, store_id=store_id, source_file=f.name)
            log.info("%s store %s: %d promotions", f.chain_key, store_id, n)
        else:
            raise ValueError(f"unexpected file type {meta.file_type}")

        loader.log_file(db, f.name, meta, "loaded", sha256=sha, size_bytes=len(data), row_count=n,
                        duration_ms=int((time.monotonic() - t0) * 1000))
        stats.loaded += 1
        stats.rows += n
    except Exception as exc:  # noqa: BLE001 - one bad file must not stop the run
        log.exception("%s: failed on %s", f.chain_key, f.name)
        loader.log_file(db, f.name, f.meta, "failed", size_bytes=len(data) or None, error=repr(exc),
                        duration_ms=int((time.monotonic() - t0) * 1000))
        stats.failed += 1
        stats.errors.append(f"{f.name}: {exc}")


def run_chain(db: Database, settings: Settings, chain_key: str, stats: RunStats) -> None:
    chain = CHAINS[chain_key]
    log.info("=== %s (%s) ===", chain.name_en, chain.chain_id)
    with make_source(chain_key, settings.http_timeout, settings.http_retries) as src:
        # 1. stores
        store_files = latest_per_store(src.list_files(FileType.STORES))
        stores: list[StoreRecord] = []
        if store_files:
            sf = max(store_files.values(), key=lambda f: f.meta.published_at or datetime.min)
            data = src.download(sf)
            save_raw(settings, sf, data)
            stores = [s for s in parse_stores(data, sf.meta) if s.chain_id == chain.chain_id]
            loader.upsert_stores(db, stores)
            log.info("%s: %d stores in stores file", chain_key, len(stores))
        else:
            log.warning("%s: no stores file found", chain_key)

        # 2. choose branches
        tracked = select_stores(chain_key, stores, settings.store_selection)
        if not tracked:
            log.warning("%s: no store matched the selection — check config/settings.yaml", chain_key)
            return
        loader.set_tracked(db, chain.chain_id, tracked)
        log.info("%s: tracking stores %s", chain_key, tracked)

        # 3. newest price / promo file per tracked branch
        for type_name in settings.file_types:
            ftype = FileType(type_name)
            files = latest_per_store(src.list_files(ftype, tracked))
            missing = set(tracked) - set(k for k in files if k is not None)
            if missing:
                log.warning("%s: no %s file for stores %s", chain_key, type_name, sorted(missing))
            for f in sorted(files.values(), key=lambda x: (x.meta.store_id or 0)):
                _process_file(db, settings, src, f, stats)


def run(settings: Settings, chains: list[str] | None = None) -> RunStats:
    db = Database(settings.database_url or "")
    stats = RunStats()
    loader.seed_chains(db)
    run_id = loader.start_run(db)
    try:
        for key in chains or settings.enabled_chains:
            try:
                run_chain(db, settings, key, stats)
            except Exception as exc:  # noqa: BLE001 - next chain still runs
                log.exception("chain %s failed", key)
                stats.failed += 1
                stats.errors.append(f"{key}: {exc}")
    finally:
        loader.finish_run(db, run_id, stats.status, stats.loaded, stats.failed, stats.rows,
                          "\n".join(stats.errors[:20]))
        db.close()
    log.info("run %d: %s — %d loaded, %d skipped, %d failed, %d rows",
             run_id, stats.status, stats.loaded, stats.skipped, stats.failed, stats.rows)
    return stats


def load_local(settings: Settings, paths: list[Path], force: bool = False) -> RunStats:
    """Load files already on disk (offline dev, backfills, tests).

    force=True reprocesses files already in the log. Safe: promotions are
    upserts, and price files older than the loaded snapshot are still refused.
    """
    from .models import FileName

    class _LocalSource(Source):
        def list_files(self, file_type, store_ids=None):
            return []

        def download(self, f):
            return Path(f.url).read_bytes()

    settings.raw_keep = False  # the files are already on disk
    db = Database(settings.database_url or "")
    stats = RunStats()
    loader.seed_chains(db)
    by_chain = {c.chain_id: c for c in CHAINS.values()}
    metas = []
    for p in paths:
        m = FileName.parse(p.name)
        if m is None or m.is_null:
            log.warning("skipping %s (not a transparency file)", p.name)
            continue
        metas.append((p, m))
    # stores first, then prices/promos in publish order (SCD2 needs chronology)
    metas.sort(key=lambda pm: (pm[1].file_type is not FileType.STORES, pm[1].published_at or datetime.min))
    try:
        for p, m in metas:
            chain = by_chain.get(m.chain_id)
            if chain is None:
                log.warning("skipping %s: chain %s is not registered", p.name, m.chain_id)
                continue
            if m.file_type is FileType.STORES:
                loader.upsert_stores(db, parse_stores(p.read_bytes(), m))
                continue
            src = _LocalSource(chain)
            _process_file(db, settings, src, RemoteFile(chain.key, p.name, str(p), m), stats, force=force)
        # every branch we have prices for counts as tracked
        db.execute(
            """UPDATE core.stores s SET is_tracked = true
               WHERE EXISTS (SELECT 1 FROM core.price_history h
                             WHERE h.chain_id = s.chain_id AND h.store_id = s.store_id)"""
        )
    finally:
        db.close()
    return stats
