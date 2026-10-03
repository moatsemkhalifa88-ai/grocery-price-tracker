from datetime import datetime

from pricetracker.config import StoreSelection
from pricetracker.models import FileName, RemoteFile, StoreRecord
from pricetracker.pipeline import select_stores
from pricetracker.sources import latest_per_store
from pricetracker.sources.shufersal import last_page, parse_listing

LISTING = """
<html><body><div id="gridContainer"><table>
<tbody>
 <tr><td><a href="https://pricesprodpublic.blob.core.windows.net/pricefull/PriceFull7290027600007-214-202610020300.gz?sv=2014&amp;sig=x">הורדה</a></td>
     <td>10/2/2026 3:00:00 AM</td><td>1.2 MB</td><td>gz</td><td>pricefull</td><td>דיל קריון</td>
     <td>PriceFull7290027600007-214-202610020300</td></tr>
 <tr><td><a href="https://pricesprodpublic.blob.core.windows.net/pricefull/PriceFull7290027600007-214-202610010300.gz?sv=2014">הורדה</a></td>
     <td>10/1/2026 3:00:00 AM</td><td>1.2 MB</td></tr>
</tbody>
<tfoot><tr><td><a href="/FileObject/UpdateCategory?catID=2&amp;page=2">2</a>
 <a href="/FileObject/UpdateCategory?catID=2&amp;page=17">&gt;&gt;</a></td></tr></tfoot>
</table></div></body></html>
"""


def test_shufersal_listing_parsed():
    rows = parse_listing(LISTING)
    assert [n for n, _ in rows] == [
        "PriceFull7290027600007-214-202610020300.gz",
        "PriceFull7290027600007-214-202610010300.gz",
    ]
    assert rows[0][1].startswith("https://pricesprodpublic.blob.core.windows.net/")
    assert last_page(LISTING) == 17


def test_latest_per_store_picks_newest():
    names = [
        "PriceFull7290027600007-214-202610010300.gz",
        "PriceFull7290027600007-214-202610020300.gz",
        "PriceFull7290027600007-005-202610020300.gz",
    ]
    files = [RemoteFile("shufersal", n, n, FileName.parse(n)) for n in names]
    best = latest_per_store(files)
    assert best[214].meta.published_at == datetime(2026, 10, 2, 3)
    assert set(best) == {214, 5}


def _store(i, city, name=""):
    return StoreRecord(chain_id="1", store_id=i, city=city, store_name=name)


def test_select_stores_by_city_name_or_address_with_limit():
    stores = [_store(1, "חיפה"), _store(2, "תל אביב"), _store(3, "3000", "רמי לוי כרמיאל"),
              _store(4, "חיפה"), _store(5, "חיפה")]
    sel = StoreSelection(cities=["חיפה", "כרמיאל"], max_stores_per_chain=3)
    assert select_stores("x", stores, sel) == [1, 3, 4]


def test_select_stores_forced_ids_always_included():
    stores = [_store(1, "חיפה"), _store(2, "תל אביב"), _store(4, "חיפה")]
    sel = StoreSelection(cities=["חיפה"], max_stores_per_chain=2, include_store_ids={"x": [2]})
    assert select_stores("x", stores, sel) == [1, 2]


def test_shufersal_listing_without_tbody_2026_names():
    """Raw server HTML has no <tbody> (browsers add it) and the 2026 name layout."""
    html = (
        '<div id="gridContainer"><table><thead><tr><th>x</th></tr></thead>'
        '<tr><td><a href="https://pricesprodpublic.blob.core.windows.net/pricefull/'
        'PriceFull7290027600007-001-004-20261002-030000.gz?sv=2014&amp;sp=r">download</a></td></tr>'
        "</table></div>"
    )
    rows = parse_listing(html)
    assert len(rows) == 1
    meta = FileName.parse(rows[0][0])
    assert meta.store_id == 4 and meta.published_at == datetime(2026, 10, 2, 3, 0)
