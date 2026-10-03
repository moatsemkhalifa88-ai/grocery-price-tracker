"""Typed records that flow through the pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class FileType(str, Enum):
    PRICE_FULL = "PriceFull"
    PRICE = "Price"
    PROMO_FULL = "PromoFull"
    PROMO = "Promo"
    STORES = "Stores"

    @property
    def is_price(self) -> bool:
        return self in (FileType.PRICE_FULL, FileType.PRICE)

    @property
    def is_promo(self) -> bool:
        return self in (FileType.PROMO_FULL, FileType.PROMO)


# Known layouts (the chains don't agree, and they change it over time):
#   PriceFull7290027600007-001-202610020300.gz          chain-store-timestamp
#   PriceFull7290027600007-001-004-20261002-030000.gz   chain-subchain-store-date-time (Shufersal, 2026)
#   Stores7290058140886-202610020500.xml                chain-timestamp
#   NULLPrice7290058108879-028-202410261441.xml         empty files some chains publish
_FILENAME_RE = re.compile(
    r"^(?:NULL)?(?P<type>PriceFull|PromoFull|Price|Promo|Stores?)"
    r"(?P<chain>\d{13})(?P<rest>(?:-\d+)+)",
    re.IGNORECASE,
)


def _split_rest(rest: str) -> tuple[int | None, str]:
    """'-001-004-20261002-030000' -> (store 4, '20261002030000')."""
    parts = [p for p in rest.split("-") if p]
    if len(parts) >= 2 and len(parts[-2]) == 8 and 4 <= len(parts[-1]) <= 6:
        ts, ids = parts[-2] + parts[-1], parts[:-2]
    else:
        ts, ids = parts[-1], parts[:-1]
    store = int(ids[-1]) if ids else None
    return store, ts


@dataclass(frozen=True)
class FileName:
    file_type: FileType
    chain_id: str
    store_id: int | None
    published_at: datetime | None
    is_null: bool

    @classmethod
    def parse(cls, name: str) -> "FileName | None":
        base = name.rsplit("/", 1)[-1]
        m = _FILENAME_RE.match(base)
        if not m:
            return None
        t = m.group("type").lower()
        file_type = {
            "pricefull": FileType.PRICE_FULL,
            "price": FileType.PRICE,
            "promofull": FileType.PROMO_FULL,
            "promo": FileType.PROMO,
            "store": FileType.STORES,
            "stores": FileType.STORES,
        }[t]
        store_id, ts = _split_rest(m.group("rest"))
        published = None
        for fmt, length in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8)):
            if len(ts) >= length:
                try:
                    published = datetime.strptime(ts[:length], fmt)
                    break
                except ValueError:
                    continue
        return cls(
            file_type=file_type,
            chain_id=m.group("chain"),
            store_id=store_id,
            published_at=published,
            is_null=base.upper().startswith("NULL"),
        )


@dataclass(frozen=True)
class RemoteFile:
    """A file a source says is available for download."""

    chain_key: str
    name: str
    url: str
    meta: FileName


@dataclass
class StoreRecord:
    chain_id: str
    store_id: int
    store_name: str | None = None
    chain_name: str | None = None
    subchain_id: str | None = None
    subchain_name: str | None = None
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    store_type: str | None = None


@dataclass
class PriceRecord:
    chain_id: str
    store_id: int
    item_code: str
    item_type: int | None
    item_name: str | None
    manufacturer_name: str | None
    manufacture_country: str | None
    unit_qty: str | None
    quantity: Decimal | None
    unit_of_measure: str | None
    is_weighted: bool | None
    qty_in_package: str | None
    item_price: Decimal
    unit_of_measure_price: Decimal | None
    allow_discount: bool | None
    item_status: int | None
    price_update_date: datetime | None


@dataclass
class PromoItem:
    """One product inside a promotion. Since 2026 the chains put the reward
    (price, quantity, rate) on each item rather than on the promotion."""
    item_code: str
    reward_type: int | None = None
    min_qty: Decimal | None = None
    discounted_price: Decimal | None = None
    price_per_unit: Decimal | None = None
    discount_rate: Decimal | None = None


@dataclass
class PromoRecord:
    chain_id: str
    store_id: int
    promotion_id: str
    description: str | None
    start_at: datetime | None
    end_at: datetime | None
    update_date: datetime | None
    reward_type: int | None
    min_qty: Decimal | None
    max_qty: Decimal | None
    discounted_price: Decimal | None
    discount_rate: Decimal | None
    min_purchase_amount: Decimal | None
    is_club_only: bool
    is_coupon: bool = False
    items: list[PromoItem] = field(default_factory=list)

    @property
    def item_codes(self) -> list[str]:
        return sorted({i.item_code for i in self.items})
