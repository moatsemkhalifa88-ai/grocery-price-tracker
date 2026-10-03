"""Parser tests against real chain files (trimmed) and format-variant fixtures."""

from decimal import Decimal
from pathlib import Path

from pricetracker.models import FileName, FileType
from pricetracker.parsing.decode import to_utf8_xml
from pricetracker.parsing.xml_parser import (
    normalize_item_code,
    parse_prices,
    parse_promos,
    parse_stores,
    to_datetime,
)

FIX = Path(__file__).parent / "fixtures"


def _load(name: str):
    return (FIX / name).read_bytes(), FileName.parse(name)


# ------------------------------------------------------------- filenames ---

def test_filename_price_full():
    m = FileName.parse("PriceFull7290027600007-001-202610020300.gz")
    assert m.file_type is FileType.PRICE_FULL
    assert m.chain_id == "7290027600007"
    assert m.store_id == 1
    assert m.published_at.strftime("%Y-%m-%d %H:%M") == "2026-10-02 03:00"


def test_filename_shufersal_2026_layout_with_subchain():
    m = FileName.parse("PriceFull7290027600007-001-004-20261002-030000.gz")
    assert m.file_type is FileType.PRICE_FULL
    assert m.store_id == 4
    assert m.published_at.strftime("%Y-%m-%d %H:%M:%S") == "2026-10-02 03:00:00"


def test_filename_cerberus_stores_without_store_id():
    m = FileName.parse("Stores7290058140886-202610020500.xml")
    assert m.file_type is FileType.STORES
    assert m.store_id is None


def test_filename_null_file_flagged():
    m = FileName.parse("NULLPrice7290058108879-028-202410261441.xml")
    assert m.is_null and m.file_type is FileType.PRICE


def test_filename_unrelated_is_none():
    assert FileName.parse("readme.txt") is None


# ---------------------------------------------------------------- decode ---

def test_truncated_gzip_is_recovered():
    # Real file whose upload was cut off mid-stream
    xml = to_utf8_xml((FIX / "PriceFull7290876100000-003-202410070010.gz").read_bytes())
    assert xml.lstrip().startswith(b"<Root>")


# ---------------------------------------------------------------- prices ---

def test_prices_item_layout_real_file():
    data, meta = _load("PriceFull7290876100000-003-202410070010.gz")
    rows = list(parse_prices(data, meta))
    assert len(rows) > 20
    milk = next(r for r in rows if r.item_code == "7290000042640")
    assert milk.item_price == Decimal("3.90")
    assert milk.store_id == 3
    assert milk.item_name.startswith("חלב")
    assert milk.manufacture_country is None  # 'לא ידוע' → NULL
    assert milk.is_weighted is False


def test_prices_line_layout_real_file():
    """Some chains use <OrderXml><Envelope>…<Line> and the 'blsWeighted' typo."""
    data, meta = _load("PriceFull7290172900007-083-202409270311.xml")
    rows = list(parse_prices(data, meta))
    assert len(rows) == 30
    assert all(r.chain_id == "7290172900007" and r.store_id == 83 for r in rows)
    assert all(r.is_weighted is not None for r in rows)
    assert all(r.item_price > 0 for r in rows)


# ------------------------------------------------------------ promotions ---

def test_promos_cp1255_with_items_and_clubs():
    data, meta = _load("PromoFull7290058140886-039-202610020010.xml")
    promos = {p.promotion_id: p for p in parse_promos(data, meta)}
    assert set(promos) == {"1188234", "1190001"}
    milk = promos["1188234"]
    assert milk.store_id == 39
    assert milk.min_qty == Decimal("2.00")
    assert milk.discounted_price == Decimal("10.00")
    assert milk.item_codes == ["7290004131074", "7290110115906"]
    assert milk.is_club_only is False
    assert milk.end_at.strftime("%H:%M") == "23:59"
    assert promos["1190001"].is_club_only is True


def test_promo_file_without_promotions_yields_nothing():
    data, meta = _load("PromoFull7290172900007-350-202410030634.xml")
    assert list(parse_promos(data, meta)) == []


# ---------------------------------------------------------------- stores ---

def test_stores_shufersal_sap_uppercase():
    data, meta = _load("Stores7290027600007-000-202610020201.xml")
    stores = {s.store_id: s for s in parse_stores(data, meta)}
    assert set(stores) == {214, 5}
    assert stores[214].city == "קרית ביאליק"
    assert stores[214].subchain_name == "שופרסל דיל"
    assert stores[214].chain_id == "7290027600007"


def test_stores_utf16_nested_subchains():
    data, meta = _load("Stores7290058140886-202610020500.xml")
    stores = {s.store_id: s for s in parse_stores(data, meta)}
    assert set(stores) == {39, 41}
    assert stores[39].subchain_name == "רמי לוי"
    assert stores[39].chain_name == "רמי לוי שיווק השקמה"
    assert stores[41].zip_code is None


# --------------------------------------------------------------- helpers ---

def test_item_code_normalization():
    assert normalize_item_code(" 07290000042640 ") == "7290000042640"
    assert normalize_item_code("000") is None


def test_datetime_formats():
    assert to_datetime("2024-05-16 22:25:16").hour == 22
    assert to_datetime("2024-05-16T22:25:16.000").minute == 25
    assert to_datetime("2026-09-28", "23:59").minute == 59
    assert to_datetime("16/05/2024").day == 16
    assert to_datetime("garbage") is None
