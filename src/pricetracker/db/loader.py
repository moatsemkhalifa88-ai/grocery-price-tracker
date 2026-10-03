"""Load parsed records into the core schema.

Prices are merged as **SCD Type 2**: a new row is written only when a price
changes, the previous row is closed (``valid_to``), and products missing from a
*full* snapshot are closed as delisted. A daily full file of ~8,000 items
usually produces a few dozen new rows instead of 8,000.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

from ..models import FileName, PriceRecord, PromoRecord, StoreRecord
from ..sources import CHAINS
from .connection import Database

log = logging.getLogger(__name__)


def product_key(chain_id: str, item_code: str, item_type: int | None = None) -> tuple[str, bool]:
    """Barcodes (8+ digits, not flagged internal) are shared across chains."""
    is_barcode = item_code.isdigit() and len(item_code) >= 8 and item_type != 0
    return (item_code if is_barcode else f"{chain_id}:{item_code}"), is_barcode


# ------------------------------------------------------------- bookkeeping --

def seed_chains(db: Database) -> None:
    for c in CHAINS.values():
        db.execute(
            """INSERT INTO core.chains (chain_id, chain_key, name_he, name_en)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (chain_id) DO UPDATE
               SET chain_key = EXCLUDED.chain_key, name_he = EXCLUDED.name_he, name_en = EXCLUDED.name_en""",
            (c.chain_id, c.key, c.name_he, c.name_en),
        )


def already_processed(db: Database, file_name: str) -> bool:
    rows = db.query(
        "SELECT 1 FROM ingest.file_log WHERE file_name = %s AND status IN ('loaded', 'skipped')",
        (file_name,),
    )
    return bool(rows)


def log_file(db: Database, file_name: str, meta: FileName, status: str, *, sha256: str | None = None,
             size_bytes: int | None = None, row_count: int | None = None, error: str | None = None,
             duration_ms: int | None = None) -> None:
    db.execute(
        """INSERT INTO ingest.file_log
               (file_name, chain_id, file_type, store_id, published_at, sha256, size_bytes,
                row_count, status, error, duration_ms, processed_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
           ON CONFLICT (file_name) DO UPDATE SET
               status = EXCLUDED.status, error = EXCLUDED.error, row_count = EXCLUDED.row_count,
               sha256 = EXCLUDED.sha256, size_bytes = EXCLUDED.size_bytes,
               duration_ms = EXCLUDED.duration_ms, processed_at = now()""",
        (file_name, meta.chain_id, meta.file_type.value, meta.store_id, meta.published_at, sha256,
         size_bytes, row_count, status, (error or "")[:2000] or None, duration_ms),
    )


def start_run(db: Database) -> int:
    return db.query("INSERT INTO ingest.run_log DEFAULT VALUES RETURNING run_id")[0][0]


def finish_run(db: Database, run_id: int, status: str, loaded: int, failed: int, rows: int, notes: str = "") -> None:
    db.execute(
        """UPDATE ingest.run_log SET finished_at = now(), status = %s, files_loaded = %s,
               files_failed = %s, rows_loaded = %s, notes = %s WHERE run_id = %s""",
        (status, loaded, failed, rows, notes or None, run_id),
    )


# ------------------------------------------------------------------ stores --

def upsert_stores(db: Database, stores: Iterable[StoreRecord]) -> int:
    rows = {(s.chain_id, s.store_id): s for s in stores}  # dedupe
    with db.transaction():
        db.execute("""CREATE TEMP TABLE stg_stores (LIKE core.stores INCLUDING DEFAULTS) ON COMMIT DROP""")
        db.copy_rows(
            "stg_stores",
            ["chain_id", "store_id", "store_name", "subchain_id", "subchain_name",
             "address", "city", "zip_code", "store_type"],
            ([s.chain_id, s.store_id, s.store_name, s.subchain_id, s.subchain_name,
              s.address, s.city, s.zip_code, s.store_type] for s in rows.values()),
        )
        n = db.execute(
            """INSERT INTO core.stores (chain_id, store_id, store_name, subchain_id, subchain_name,
                                        address, city, zip_code, store_type)
               SELECT chain_id, store_id, store_name, subchain_id, subchain_name,
                      address, city, zip_code, store_type
               FROM stg_stores
               WHERE chain_id IN (SELECT chain_id FROM core.chains)
               ON CONFLICT (chain_id, store_id) DO UPDATE SET
                   store_name    = COALESCE(EXCLUDED.store_name, core.stores.store_name),
                   subchain_id   = COALESCE(EXCLUDED.subchain_id, core.stores.subchain_id),
                   subchain_name = COALESCE(EXCLUDED.subchain_name, core.stores.subchain_name),
                   address       = COALESCE(EXCLUDED.address, core.stores.address),
                   city          = COALESCE(EXCLUDED.city, core.stores.city),
                   zip_code      = COALESCE(EXCLUDED.zip_code, core.stores.zip_code),
                   store_type    = COALESCE(EXCLUDED.store_type, core.stores.store_type),
                   last_seen_at  = now()"""
        )
    return n


def set_tracked(db: Database, chain_id: str, store_ids: Iterable[int]) -> None:
    ids = sorted(set(store_ids))
    with db.transaction():
        db.execute("UPDATE core.stores SET is_tracked = false WHERE chain_id = %s", (chain_id,))
        if ids:
            db.execute(
                "UPDATE core.stores SET is_tracked = true WHERE chain_id = %s AND store_id = ANY(%s)",
                (chain_id, ids),
            )


def _ensure_store(db: Database, chain_id: str, store_id: int) -> None:
    db.execute(
        """INSERT INTO core.stores (chain_id, store_id) VALUES (%s, %s)
           ON CONFLICT (chain_id, store_id) DO NOTHING""",
        (chain_id, store_id),
    )


# ------------------------------------------------------------------ prices --

def latest_snapshot(db: Database, chain_id: str, store_id: int) -> datetime | None:
    rows = db.query(
        "SELECT max(valid_from) FROM core.price_history WHERE chain_id = %s AND store_id = %s",
        (chain_id, store_id),
    )
    return rows[0][0] if rows else None


_PRICE_COLS = [
    "product_key", "item_code", "is_barcode", "item_name", "manufacturer_name", "manufacture_country",
    "unit_qty", "quantity", "unit_of_measure", "is_weighted", "item_price", "unit_of_measure_price",
    "allow_discount", "item_status", "price_update_date",
]


def load_prices(db: Database, records: Iterable[PriceRecord], *, chain_id: str, store_id: int,
                snapshot_at: datetime, source_file: str, is_full: bool) -> dict[str, int]:
    """SCD2 merge of one store's price file. Returns counts of what changed."""

    def rows():
        for r in records:
            key, is_bc = product_key(chain_id, r.item_code, r.item_type)
            yield [key, r.item_code, is_bc, r.item_name, r.manufacturer_name, r.manufacture_country,
                   r.unit_qty, r.quantity, r.unit_of_measure, r.is_weighted, r.item_price,
                   r.unit_of_measure_price, r.allow_discount, r.item_status, r.price_update_date]

    p = {"chain": chain_id, "store": store_id, "ts": snapshot_at, "file": source_file}
    records = list(records)
    if not records:
        raise ValueError("price file contains no valid items")
    with db.transaction():
        _ensure_store(db, chain_id, store_id)
        db.execute(
            """CREATE TEMP TABLE stg_prices (
                   product_key text, item_code text, is_barcode boolean, item_name text,
                   manufacturer_name text, manufacture_country text, unit_qty text,
                   quantity numeric, unit_of_measure text, is_weighted boolean,
                   item_price numeric(10,2), unit_of_measure_price numeric, allow_discount boolean,
                   item_status smallint, price_update_date timestamp
               ) ON COMMIT DROP"""
        )
        staged = db.copy_rows("stg_prices", _PRICE_COLS, rows())

        # one row per product (a few chains list the same item twice)
        db.execute(
            """CREATE TEMP TABLE stg_p ON COMMIT DROP AS
               SELECT DISTINCT ON (product_key) *
               FROM stg_prices
               ORDER BY product_key, price_update_date DESC NULLS LAST, item_price"""
        )

        db.execute(
            """INSERT INTO core.products AS p
                   (product_key, item_code, is_barcode, owner_chain_id, item_name, manufacturer_name,
                    manufacture_country, unit_qty, quantity, unit_of_measure, is_weighted)
               SELECT product_key, item_code, is_barcode,
                      CASE WHEN is_barcode THEN NULL ELSE %(chain)s END,
                      item_name, manufacturer_name, manufacture_country, unit_qty,
                      quantity, unit_of_measure, is_weighted
               FROM stg_p
               ON CONFLICT (product_key) DO UPDATE SET
                   item_name           = COALESCE(p.item_name, EXCLUDED.item_name),
                   manufacturer_name   = COALESCE(p.manufacturer_name, EXCLUDED.manufacturer_name),
                   manufacture_country = COALESCE(p.manufacture_country, EXCLUDED.manufacture_country),
                   unit_qty            = COALESCE(p.unit_qty, EXCLUDED.unit_qty),
                   quantity            = COALESCE(p.quantity, EXCLUDED.quantity),
                   unit_of_measure     = COALESCE(p.unit_of_measure, EXCLUDED.unit_of_measure),
                   is_weighted         = COALESCE(p.is_weighted, EXCLUDED.is_weighted),
                   last_seen_at        = now()""",
            p,
        )

        changed = db.execute(
            """UPDATE core.price_history h SET valid_to = %(ts)s
               FROM stg_p s
               WHERE h.chain_id = %(chain)s AND h.store_id = %(store)s
                 AND h.product_key = s.product_key AND h.valid_to IS NULL
                 AND h.valid_from < %(ts)s AND h.item_price <> s.item_price""",
            p,
        )

        # Safety valve: a truncated or half-empty "full" file must not wipe the
        # shelf. If it lists under half of what is currently open, treat it as a
        # partial update (prices still merge, nothing is delisted).
        open_now = db.query(
            """SELECT count(*) FROM core.price_history
               WHERE chain_id = %(chain)s AND store_id = %(store)s AND valid_to IS NULL""",
            p,
        )[0][0]
        if is_full and open_now >= 20 and staged < 0.5 * open_now:
            log.warning("%s: full file lists %d items but %d are on the shelf — not delisting",
                        source_file, staged, open_now)
            is_full = False

        delisted = 0
        if is_full:
            delisted = db.execute(
                """UPDATE core.price_history h SET valid_to = %(ts)s
                   WHERE h.chain_id = %(chain)s AND h.store_id = %(store)s
                     AND h.valid_to IS NULL AND h.valid_from < %(ts)s
                     AND NOT EXISTS (SELECT 1 FROM stg_p s WHERE s.product_key = h.product_key)""",
                p,
            )

        inserted = db.execute(
            """INSERT INTO core.price_history
                   (chain_id, store_id, product_key, item_price, unit_of_measure_price, chain_item_name,
                    allow_discount, item_status, price_update_date, valid_from, valid_to, source_file)
               SELECT %(chain)s, %(store)s, s.product_key, s.item_price, s.unit_of_measure_price,
                      s.item_name, s.allow_discount, s.item_status, s.price_update_date,
                      %(ts)s, NULL, %(file)s
               FROM stg_p s
               WHERE NOT EXISTS (
                   SELECT 1 FROM core.price_history h
                   WHERE h.chain_id = %(chain)s AND h.store_id = %(store)s
                     AND h.product_key = s.product_key AND h.valid_to IS NULL)""",
            p,
        )
    return {"staged": staged, "inserted": inserted, "price_changes": changed, "delisted": delisted,
            "new_products": max(inserted - changed, 0)}


# -------------------------------------------------------------- promotions --

def load_promos(db: Database, records: Iterable[PromoRecord], *, chain_id: str, store_id: int,
                source_file: str) -> int:
    promos = {r.promotion_id: r for r in records}
    with db.transaction():
        _ensure_store(db, chain_id, store_id)
        db.execute(
            """CREATE TEMP TABLE stg_promos (
                   promotion_id text, description text, start_at timestamp, end_at timestamp,
                   update_date timestamp, reward_type smallint, min_qty numeric, max_qty numeric,
                   discounted_price numeric(10,2), discount_rate numeric(10,2),
                   min_purchase_amount numeric(10,2), is_club_only boolean, is_coupon boolean,
                   item_count integer
               ) ON COMMIT DROP"""
        )
        db.copy_rows(
            "stg_promos",
            ["promotion_id", "description", "start_at", "end_at", "update_date", "reward_type",
             "min_qty", "max_qty", "discounted_price", "discount_rate", "min_purchase_amount",
             "is_club_only", "is_coupon", "item_count"],
            ([r.promotion_id, r.description, r.start_at, r.end_at, r.update_date, r.reward_type,
              r.min_qty, r.max_qty, r.discounted_price, r.discount_rate, r.min_purchase_amount,
              r.is_club_only, r.is_coupon, len(r.items)] for r in promos.values()),
        )
        db.execute(
            """CREATE TEMP TABLE stg_promo_items (
                   promotion_id text, item_code text, reward_type smallint, min_qty numeric,
                   discounted_price numeric(10,2), price_per_unit numeric(12,4), discount_rate numeric(10,2)
               ) ON COMMIT DROP"""
        )
        db.copy_rows(
            "stg_promo_items",
            ["promotion_id", "item_code", "reward_type", "min_qty", "discounted_price",
             "price_per_unit", "discount_rate"],
            ([r.promotion_id, i.item_code, i.reward_type, i.min_qty, i.discounted_price,
              i.price_per_unit, i.discount_rate] for r in promos.values() for i in r.items),
        )
        p = {"chain": chain_id, "store": store_id, "file": source_file}
        db.execute(
            """INSERT INTO core.promotions AS t
                   (chain_id, store_id, promotion_id, description, start_at, end_at, update_date,
                    reward_type, min_qty, max_qty, discounted_price, discount_rate,
                    min_purchase_amount, is_club_only, is_coupon, item_count, source_file)
               SELECT %(chain)s, %(store)s, promotion_id, description, start_at, end_at, update_date,
                      reward_type, min_qty, max_qty, discounted_price, discount_rate,
                      min_purchase_amount, is_club_only, is_coupon, item_count, %(file)s
               FROM stg_promos
               ON CONFLICT (chain_id, store_id, promotion_id) DO UPDATE SET
                   description = EXCLUDED.description, start_at = EXCLUDED.start_at,
                   end_at = EXCLUDED.end_at, update_date = EXCLUDED.update_date,
                   reward_type = EXCLUDED.reward_type, min_qty = EXCLUDED.min_qty,
                   max_qty = EXCLUDED.max_qty, discounted_price = EXCLUDED.discounted_price,
                   discount_rate = EXCLUDED.discount_rate,
                   min_purchase_amount = EXCLUDED.min_purchase_amount,
                   is_club_only = EXCLUDED.is_club_only, is_coupon = EXCLUDED.is_coupon,
                   item_count = EXCLUDED.item_count,
                   source_file = EXCLUDED.source_file, last_seen_at = now()""",
            p,
        )
        db.execute(
            """DELETE FROM core.promotion_items
               WHERE chain_id = %(chain)s AND store_id = %(store)s
                 AND promotion_id IN (SELECT promotion_id FROM stg_promos)""",
            p,
        )
        # map promo item codes onto product keys: the chain's internal code if we
        # know it, otherwise the shared barcode
        db.execute(
            """INSERT INTO core.promotion_items
                   (chain_id, store_id, promotion_id, product_key, reward_type, min_qty,
                    discounted_price, price_per_unit, discount_rate)
               SELECT DISTINCT ON (i.promotion_id, k.product_key)
                      %(chain)s, %(store)s, i.promotion_id, k.product_key, i.reward_type, i.min_qty,
                      i.discounted_price, i.price_per_unit, i.discount_rate
               FROM stg_promo_items i
               CROSS JOIN LATERAL (SELECT
                      CASE
                          WHEN EXISTS (SELECT 1 FROM core.products p
                                       WHERE p.product_key = %(chain)s || ':' || i.item_code)
                              THEN %(chain)s || ':' || i.item_code
                          WHEN i.item_code ~ '^[0-9]{8,}$' THEN i.item_code
                          ELSE %(chain)s || ':' || i.item_code
                      END AS product_key) k
               ORDER BY i.promotion_id, k.product_key""",
            p,
        )
    return len(promos)
