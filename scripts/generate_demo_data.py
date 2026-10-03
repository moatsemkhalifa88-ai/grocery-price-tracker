"""Generate SYNTHETIC transparency files for local development.

Real history takes weeks to accumulate, so this script fakes ~45 days for all
five chains so you can build and test dbt models and dashboards right away.
Barcodes start with 7299999 (not real products) and prices are random walks.

    python scripts/generate_demo_data.py            # writes data/demo/
    python -m pricetracker load data/demo           # into a *dev* database

Never load demo data into the database behind your public dashboard.
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from pricetracker.sources import CHAINS  # noqa: E402
from xml_builders import price_full_xml, promo_full_xml, stores_xml  # noqa: E402

PRODUCTS = [
    # name, base price, manufacturer, quantity, unit
    ("חלב טרי 3% קרטון 1 ליטר", 6.9, "מחלבה א", 1000, "מיליליטרים"),
    ("חלב טרי 1% קרטון 1 ליטר", 6.9, "מחלבה א", 1000, "מיליליטרים"),
    ("גבינה לבנה 5% 250 גרם", 5.9, "מחלבה א", 250, "גרמים"),
    ("גבינה צהובה פרוסה 200 גרם", 14.9, "מחלבה ב", 200, "גרמים"),
    ("יוגורט טבעי 3% 200 גרם", 3.9, "מחלבה ב", 200, "גרמים"),
    ("קוטג' 5% 250 גרם", 6.5, "מחלבה א", 250, "גרמים"),
    ("שמנת חמוצה 15% 200 מל", 4.9, "מחלבה ב", 200, "מיליליטרים"),
    ("חמאה 200 גרם", 9.9, "מחלבה א", 200, "גרמים"),
    ("ביצים L תריסר", 13.9, "משק ביצים", 12, "יחידה"),
    ("לחם אחיד פרוס 750 גרם", 7.5, "מאפייה א", 750, "גרמים"),
    ("לחם מלא 500 גרם", 12.9, "מאפייה ב", 500, "גרמים"),
    ("פיתות 10 יחידות", 8.9, "מאפייה א", 10, "יחידה"),
    ("חטיף בוטנים 80 גרם", 4.9, "חטיפים בעמ", 80, "גרמים"),
    ("חטיף תירס 70 גרם", 4.5, "חטיפים בעמ", 70, "גרמים"),
    ("שוקולד חלב 100 גרם", 6.9, "ממתקים בעמ", 100, "גרמים"),
    ("עוגיות שוקולד צ'יפס 400 גרם", 14.9, "ממתקים בעמ", 400, "גרמים"),
    ("קפה נמס 200 גרם", 26.9, "קפה ישראלי", 200, "גרמים"),
    ("קפה טורקי 250 גרם", 13.9, "קפה ישראלי", 250, "גרמים"),
    ("תה ירוק 25 שקיקים", 11.9, "תה בעמ", 25, "יחידה"),
    ("משקה קולה 1.5 ליטר", 7.9, "משקאות בעמ", 1500, "מיליליטרים"),
    ("מים מינרליים 6x1.5 ליטר", 12.9, "מעיינות", 9000, "מיליליטרים"),
    ("מיץ תפוזים 1 ליטר", 11.9, "משקאות בעמ", 1000, "מיליליטרים"),
    ("שמן קנולה 1 ליטר", 10.9, "שמנים בעמ", 1000, "מיליליטרים"),
    ("שמן זית כתית 750 מל", 34.9, "שמנים בעמ", 750, "מיליליטרים"),
    ("אורז פרסי 1 קג", 9.9, "דגנים בעמ", 1000, "גרמים"),
    ("פסטה פנה 500 גרם", 5.9, "דגנים בעמ", 500, "גרמים"),
    ("קמח לבן 1 קג", 5.5, "דגנים בעמ", 1000, "גרמים"),
    ("סוכר לבן 1 קג", 5.9, "סוכר בעמ", 1000, "גרמים"),
    ("טחינה גולמית 500 גרם", 14.9, "טחינה בעמ", 500, "גרמים"),
    ("חומוס מוכן 400 גרם", 7.9, "סלטים בעמ", 400, "גרמים"),
    ("רסק עגבניות 100 גרם", 2.9, "שימורים בעמ", 100, "גרמים"),
    ("טונה בשמן 4 יחידות", 21.9, "שימורים בעמ", 4, "יחידה"),
    ("תירס מתוק שימורים 340 גרם", 5.9, "שימורים בעמ", 340, "גרמים"),
    ("קורנפלקס 750 גרם", 18.9, "דגנים בעמ", 750, "גרמים"),
    ("חזה עוף טרי 1 קג", 39.9, "עוף בעמ", 1000, "גרמים"),
    ("שניצל קפוא 1 קג", 34.9, "עוף בעמ", 1000, "גרמים"),
    ("נקניקיות 400 גרם", 16.9, "בשר בעמ", 400, "גרמים"),
    ("אבקת כביסה 3 קג", 39.9, "ניקיון בעמ", 3000, "גרמים"),
    ("נוזל כלים 1 ליטר", 9.9, "ניקיון בעמ", 1000, "מיליליטרים"),
    ("אקונומיקה 4 ליטר", 12.9, "ניקיון בעמ", 4000, "מיליליטרים"),
    ("נייר טואלט 32 גלילים", 44.9, "נייר בעמ", 32, "יחידה"),
    ("מגבונים לחים 72 יחידות", 9.9, "נייר בעמ", 72, "יחידה"),
    ("שמפו 700 מל", 19.9, "טיפוח בעמ", 700, "מיליליטרים"),
    ("משחת שיניים 100 מל", 12.9, "טיפוח בעמ", 100, "מיליליטרים"),
    ("חיתולים מידה 4 52 יחידות", 54.9, "תינוקות בעמ", 52, "יחידה"),
    ("מלפפון במשקל", 5.9, "ירקות", 1000, "גרמים"),
    ("עגבניה במשקל", 7.9, "ירקות", 1000, "גרמים"),
    ("בננה במשקל", 8.9, "פירות", 1000, "גרמים"),
    ("תפוח עץ במשקל", 9.9, "פירות", 1000, "גרמים"),
    ("בצל יבש במשקל", 4.9, "ירקות", 1000, "גרמים"),
]

# chain-level price personality: discounters are cheaper
CHAIN_LEVEL = {"shufersal": 1.06, "rami_levy": 0.93, "osher_ad": 0.95, "yohananof": 0.98, "tiv_taam": 1.08}
CITIES = ["חיפה", "כרמיאל", "נצרת", "עכו", "קרית ביאליק", "שפרעם", "טמרה"]


def barcode(i: int) -> str:
    return f"7299999{i:06d}"


def main(days: int = 45, out: Path = ROOT / "data" / "demo", seed: int = 7) -> None:
    rnd = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    start = datetime.now().replace(hour=3, minute=0, second=0, microsecond=0) - timedelta(days=days)
    count = 0
    for key, chain in CHAINS.items():
        store_ids = rnd.sample(range(1, 400), 3)
        cities = rnd.sample(CITIES, 3)
        stores = [{"id": s, "name": f"{chain.name_he} {c}", "city": c, "address": f"רחוב הדגמה {s}"}
                  for s, c in zip(store_ids, cities)]
        (out / f"Stores{chain.chain_id}-{start:%Y%m%d%H%M}.xml").write_bytes(
            stores_xml(chain.chain_id, chain.name_he, stores))
        # each chain carries ~85% of the catalogue
        catalogue = [i for i in range(len(PRODUCTS)) if rnd.random() < 0.85 or i < 25]
        for s in store_ids:
            store_bias = rnd.uniform(0.98, 1.03)
            prices = {i: round(PRODUCTS[i][1] * CHAIN_LEVEL[key] * store_bias * rnd.uniform(0.95, 1.05), 1) - 0.01
                      for i in catalogue}
            for d in range(days):
                day = start + timedelta(days=d)
                for i in catalogue:
                    r = rnd.random()
                    if r < 0.012:
                        prices[i] = round(prices[i] * rnd.uniform(1.02, 1.09), 1) - 0.01   # increase
                    elif r < 0.016:
                        prices[i] = round(prices[i] * rnd.uniform(0.92, 0.98), 1) - 0.01   # decrease
                    if d == 30 and rnd.random() < 0.15:  # a mid-period wave of hikes
                        prices[i] = round(prices[i] * 1.05, 1) - 0.01
                items = [{"code": barcode(i), "name": PRODUCTS[i][0], "price": max(prices[i], 0.9),
                          "manufacturer": PRODUCTS[i][2], "quantity": PRODUCTS[i][3],
                          "unit_qty": PRODUCTS[i][4], "weighted": "במשקל" in PRODUCTS[i][0]}
                         for i in catalogue if not (d == 20 and i == catalogue[-1])]
                (out / f"PriceFull{chain.chain_id}-{s:03d}-{day:%Y%m%d%H%M}.xml").write_bytes(
                    price_full_xml(chain.chain_id, s, items, day))
                count += 1
            # one promo file per store, newest snapshot
            promo_items = rnd.sample(catalogue, 6)
            last = start + timedelta(days=days - 1)
            promos = []
            for n, i in enumerate(promo_items):
                multi = n % 2 == 0
                regular = prices[i]
                promos.append({
                    "id": f"{s}{n:03d}", "codes": [barcode(i)],
                    "desc": f"{PRODUCTS[i][0][:18]} {'2 ב-' if multi else 'ב-'}{regular * (1.6 if multi else 0.85):.0f}",
                    "price": round(regular * (1.6 if multi else 0.85), 0), "min_qty": 2 if multi else 1,
                    "start": last - timedelta(days=3), "end": last + timedelta(days=7),
                    "club": 3 if n == 5 else 0,
                })
            (out / f"PromoFull{chain.chain_id}-{s:03d}-{last:%Y%m%d}0010.xml").write_bytes(
                promo_full_xml(chain.chain_id, s, promos))
    print(f"wrote {count} price files for {len(CHAINS)} chains to {out}")


if __name__ == "__main__":
    main()
