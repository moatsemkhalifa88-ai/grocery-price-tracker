"""End-to-end load into a real Postgres. Runs only when TEST_DATABASE_URL is set:

    TEST_DATABASE_URL=postgresql://user:pass@localhost/prices_test pytest tests/test_scd2_integration.py

WARNING: the test drops and recreates the core / ingest / analytics schemas.
"""

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from pricetracker.config import Settings
from pricetracker.db.connection import Database
from pricetracker.db.migrate import migrate
from pricetracker.pipeline import load_local

from xml_builders import price_full_xml, promo_full_xml, stores_xml

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set")

RAMI = "7290058140886"
MILK, BREAD, BAMBA, COFFEE = "7290004131074", "7290000066318", "7290000064659", "7290000066999"


def _reset(db: Database) -> None:
    db.execute("DROP SCHEMA IF EXISTS core, ingest, analytics, marts CASCADE")
    migrate(db)


def _write(tmp: Path, name: str, data: bytes) -> Path:
    p = tmp / name
    p.write_bytes(data)
    return p


def test_scd2_price_history(tmp_path):
    os.environ["DATABASE_URL"] = URL
    db = Database(URL)
    _reset(db)

    files = [
        _write(tmp_path, f"Stores{RAMI}-202610010500.xml",
               stores_xml(RAMI, "רמי לוי", [{"id": 39, "name": "כרמיאל", "city": "כרמיאל"}])),
        # day 1: three products
        _write(tmp_path, f"PriceFull{RAMI}-039-202610010300.xml", price_full_xml(RAMI, 39, [
            {"code": MILK, "name": "חלב 3%", "price": 6.90},
            {"code": BREAD, "name": "לחם אחיד", "price": 7.50},
            {"code": BAMBA, "name": "במבה 80 גרם", "price": 4.90},
        ], datetime(2026, 10, 1, 3))),
        # day 2: milk price up, bread unchanged, bamba gone, coffee new
        _write(tmp_path, f"PriceFull{RAMI}-039-202610020300.xml", price_full_xml(RAMI, 39, [
            {"code": MILK, "name": "חלב 3%", "price": 7.20},
            {"code": BREAD, "name": "לחם אחיד", "price": 7.50},
            {"code": COFFEE, "name": "קפה נמס", "price": 24.90},
        ], datetime(2026, 10, 2, 3))),
        _write(tmp_path, f"PromoFull{RAMI}-039-202610020010.xml", promo_full_xml(RAMI, 39, [
            {"id": "P1", "desc": "חלב 2 ב-12", "codes": [MILK], "price": 12, "min_qty": 2,
             "start": datetime(2026, 10, 1), "end": datetime(2026, 10, 10)},
        ])),
    ]
    stats = load_local(Settings.load(), files)
    assert stats.failed == 0, stats.errors
    assert stats.loaded == 3

    hist = {(r[0], r[1]): r[2] for r in db.query(
        "SELECT product_key, valid_from::date::text, valid_to FROM core.price_history")}
    # milk: closed day-1 row + open day-2 row
    assert hist[(MILK, "2026-10-01")] == datetime(2026, 10, 2, 3)
    assert hist[(MILK, "2026-10-02")] is None
    # bread unchanged → still one open row from day 1 (no duplicate written)
    assert hist[(BREAD, "2026-10-01")] is None
    assert (BREAD, "2026-10-02") not in hist
    # bamba delisted → closed
    assert hist[(BAMBA, "2026-10-01")] == datetime(2026, 10, 2, 3)
    # coffee new
    assert hist[(COFFEE, "2026-10-02")] is None
    assert len(hist) == 5

    current = dict(db.query(
        "SELECT product_key, item_price FROM core.price_history WHERE valid_to IS NULL"))
    assert current == {MILK: Decimal("7.20"), BREAD: Decimal("7.50"), COFFEE: Decimal("24.90")}

    promo_items = db.query("SELECT promotion_id, product_key FROM core.promotion_items")
    assert promo_items == [("P1", MILK)]

    # idempotent: loading the same files again changes nothing
    again = load_local(Settings.load(), files)
    assert again.loaded == 0 and again.skipped == 3
    assert db.query("SELECT count(*) FROM core.price_history")[0][0] == 5

    # an older snapshot arriving late is refused instead of corrupting history
    late = _write(tmp_path, f"PriceFull{RAMI}-039-202609300300.xml", price_full_xml(
        RAMI, 39, [{"code": MILK, "name": "חלב 3%", "price": 5.00}], datetime(2026, 9, 30, 3)))
    late_stats = load_local(Settings.load(), [late])
    assert late_stats.skipped == 1
    assert db.query("SELECT count(*) FROM core.price_history")[0][0] == 5
    db.close()


def test_truncated_full_file_does_not_delist(tmp_path):
    os.environ["DATABASE_URL"] = URL
    db = Database(URL)
    _reset(db)
    items = [{"code": f"72999990{i:05d}", "name": f"מוצר {i}", "price": 5 + i} for i in range(30)]
    day1 = _write(tmp_path, f"PriceFull{RAMI}-039-202610010300.xml",
                  price_full_xml(RAMI, 39, items, datetime(2026, 10, 1, 3)))
    # day 2 arrives cut off: only 5 of 30 items, one of them with a new price
    cut = [dict(it) for it in items[:5]]
    cut[0]["price"] = 99
    day2 = _write(tmp_path, f"PriceFull{RAMI}-039-202610020300.xml",
                  price_full_xml(RAMI, 39, cut, datetime(2026, 10, 2, 3)))
    stats = load_local(Settings.load(), [day1, day2])
    assert stats.failed == 0, stats.errors
    open_rows = db.query("SELECT count(*) FROM core.price_history WHERE valid_to IS NULL")[0][0]
    assert open_rows == 30            # nothing delisted
    assert db.query("SELECT count(*) FROM core.price_history")[0][0] == 31  # the one real change kept
    db.close()


def test_empty_price_file_is_logged_as_failed(tmp_path):
    os.environ["DATABASE_URL"] = URL
    db = Database(URL)
    _reset(db)
    empty = _write(tmp_path, f"PriceFull{RAMI}-039-202610010300.xml",
                   price_full_xml(RAMI, 39, [], datetime(2026, 10, 1, 3)))
    stats = load_local(Settings.load(), [empty])
    assert stats.failed == 1
    status = db.query("SELECT status FROM ingest.file_log")[0][0]
    assert status == "failed"
    db.close()
