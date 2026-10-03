"""One schema-tolerant parser for every chain's Price / Promo / Stores XML.

Instead of one hand-written parser per chain, we look for *shapes*:

* a price item is any element with a direct ``ItemCode`` child and an ``ItemPrice`` child
  (``<Item>`` for most chains, ``<Line>`` for some, ``<ITEM>`` elsewhere)
* a promotion is any element with a direct ``PromotionId`` child
* a store is any element with a direct ``StoreId`` child plus a name/address/city

Tag names are compared case-insensitively and without namespaces, which covers
``<STOREID>`` (Shufersal's SAP export), ``<StoreID>`` and ``<StoreId>``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

from lxml import etree

from ..models import FileName, PriceRecord, PromoItem, PromoRecord, StoreRecord
from .decode import to_utf8_xml

_PARSER = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False, no_network=True)

UNKNOWN_VALUES = {"", "לא ידוע", "unknown", "none", "null", "0"}


# ---------------------------------------------------------------- helpers ---

def _tag(el: etree._Element) -> str:
    tag = el.tag
    if not isinstance(tag, str):  # comments / processing instructions
        return ""
    return etree.QName(tag).localname.lower()


def _children(el: etree._Element) -> dict[str, str]:
    """Direct children as {lower_tag: stripped_text}. First occurrence wins."""
    out: dict[str, str] = {}
    for child in el:
        t = _tag(child)
        if t and t not in out and len(child) == 0:
            out[t] = (child.text or "").strip()
    return out


def _get(d: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        v = d.get(k)
        if v is not None and v != "":
            return v
    return None


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return None if value.lower() in UNKNOWN_VALUES - {"0"} else value


def to_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    value = value.replace(",", "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def to_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = ""
    for ch in value.strip():
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def to_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.strip().lower() in {"1", "true", "yes", "y"}


_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%Y%m%d%H%M%S",
    "%Y%m%d%H%M",
    "%Y%m%d",
)


def to_datetime(value: str | None, time_part: str | None = None) -> datetime | None:
    if not value:
        return None
    value = value.strip().split(".")[0].replace("Z", "")
    if time_part and len(value) <= 10:
        value = f"{value} {time_part.strip()[:8]}"
    for fmt in _DT_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if dt.year < 1990 or dt.year > 2100:
            return None
        return dt
    return None


def normalize_item_code(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip()
    if not code.isdigit():
        return code or None
    # barcodes are compared as strings; drop leading zeros so 0729... == 729...
    stripped = code.lstrip("0")
    return stripped or None


def _header(root: etree._Element) -> dict[str, str]:
    """ChainId / StoreId etc. can sit at root level or inside an <Envelope>."""
    found: dict[str, str] = {}
    wanted = {"chainid", "subchainid", "storeid", "chainname", "subchainname"}
    for el in root.iter():
        t = _tag(el)
        if t in wanted and t not in found and len(el) == 0 and (el.text or "").strip():
            found[t] = el.text.strip()
        if len(found) == len(wanted):
            break
    return found


def load_root(data: bytes) -> etree._Element:
    xml = to_utf8_xml(data)
    root = etree.fromstring(xml, parser=_PARSER)
    if root is None:
        raise ValueError("unparseable XML")
    return root


# ----------------------------------------------------------------- prices ---

def parse_prices(data: bytes, meta: FileName) -> Iterator[PriceRecord]:
    root = load_root(data)
    head = _header(root)
    chain_id = head.get("chainid") or meta.chain_id
    store_id = to_int(head.get("storeid"))
    if store_id is None:
        store_id = meta.store_id
    if store_id is None:
        raise ValueError("price file without a store id")

    for el in root.iter():
        if len(el) < 3:
            continue
        d = _children(el)
        if "itemcode" not in d or "itemprice" not in d:
            continue
        code = normalize_item_code(d.get("itemcode"))
        price = to_decimal(d.get("itemprice"))
        if not code or price is None or price <= 0:
            continue
        yield PriceRecord(
            chain_id=chain_id,
            store_id=store_id,
            item_code=code,
            item_type=to_int(d.get("itemtype")),
            item_name=clean_text(_get(d, "itemname", "itemnm", "manufactureritemdescription")),
            manufacturer_name=clean_text(_get(d, "manufacturername", "manufacturename")),
            manufacture_country=clean_text(_get(d, "manufacturecountry", "manufacturercountry")),
            unit_qty=clean_text(d.get("unitqty")),
            quantity=to_decimal(d.get("quantity")),
            unit_of_measure=clean_text(d.get("unitofmeasure")),
            is_weighted=to_bool(_get(d, "bisweighted", "blsweighted", "isweighted")),
            qty_in_package=clean_text(d.get("qtyinpackage")),
            item_price=price,
            unit_of_measure_price=to_decimal(d.get("unitofmeasureprice")),
            allow_discount=to_bool(d.get("allowdiscount")),
            item_status=to_int(d.get("itemstatus")),
            price_update_date=to_datetime(_get(d, "priceupdatedate", "priceupdatetime")),
        )


# ------------------------------------------------------------- promotions ---

def _promo_items(promo_el: etree._Element, defaults: dict[str, str]) -> list[PromoItem]:
    """Every element under the promotion that has an ItemCode child is an item.

    Item-level reward fields win; promotion-level ones (the pre-2026 layout)
    are the fallback. Duplicate codes keep the first occurrence.
    """
    items: dict[str, PromoItem] = {}

    def field_(d: dict[str, str], *keys: str) -> str | None:
        return _get(d, *keys) or _get(defaults, *keys)

    for el in promo_el.iter():
        if el is promo_el:
            continue
        d = _children(el)
        if "itemcode" not in d:
            continue
        code = normalize_item_code(d["itemcode"])
        if not code or code in items:
            continue
        items[code] = PromoItem(
            item_code=code,
            reward_type=to_int(field_(d, "rewardtype")),
            min_qty=to_decimal(field_(d, "minqty")),
            discounted_price=to_decimal(field_(d, "discountedprice")),
            price_per_unit=to_decimal(field_(d, "discountedpricepermida")),
            discount_rate=to_decimal(field_(d, "discountrate")),
        )
    return list(items.values())


def _min_purchase(promo_el: etree._Element) -> Decimal | None:
    """'Spend over X' threshold; lives on the promotion or on its <Group>."""
    vals = [to_decimal(el.text) for el in promo_el.iter()
            if _tag(el) in ("minpurchaseamnt", "minpurchaseamount")]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def _club_only(promo_el: etree._Element) -> bool:
    """ClubId 0 means 'all customers'. Anything else is a loyalty-club deal."""
    club_ids = [to_int(el.text) for el in promo_el.iter() if _tag(el) == "clubid"]
    club_ids = [c for c in club_ids if c is not None]
    return bool(club_ids) and all(c != 0 for c in club_ids)


def parse_promos(data: bytes, meta: FileName) -> Iterator[PromoRecord]:
    root = load_root(data)
    head = _header(root)
    chain_id = head.get("chainid") or meta.chain_id
    store_id = to_int(head.get("storeid"))
    if store_id is None:
        store_id = meta.store_id
    if store_id is None:
        raise ValueError("promo file without a store id")

    for el in root.iter():
        d = _children(el)
        if "promotionid" not in d:
            continue
        promo_id = d["promotionid"].strip()
        if not promo_id:
            continue
        yield PromoRecord(
            chain_id=chain_id,
            store_id=store_id,
            promotion_id=promo_id,
            description=clean_text(d.get("promotiondescription")),
            start_at=to_datetime(d.get("promotionstartdatetime"))
            or to_datetime(d.get("promotionstartdate"), d.get("promotionstarthour")),
            end_at=to_datetime(d.get("promotionenddatetime"))
            or to_datetime(d.get("promotionenddate"), d.get("promotionendhour")),
            update_date=to_datetime(_get(d, "promotionupdatetime", "promotionupdatedate")),
            reward_type=to_int(d.get("rewardtype")),
            min_qty=to_decimal(d.get("minqty")),
            max_qty=to_decimal(d.get("maxqty")),
            discounted_price=to_decimal(d.get("discountedprice")),
            discount_rate=to_decimal(d.get("discountrate")),
            min_purchase_amount=_min_purchase(el),
            is_club_only=_club_only(el),
            is_coupon=to_bool(d.get("additionaliscoupon")) or False,
            items=_promo_items(el, d),
        )


# ----------------------------------------------------------------- stores ---

def parse_stores(data: bytes, meta: FileName) -> Iterator[StoreRecord]:
    root = load_root(data)
    head = _header(root)
    chain_id_default = head.get("chainid") or meta.chain_id
    chain_name_default = clean_text(head.get("chainname"))

    for el in root.iter():
        d = _children(el)
        if "storeid" not in d:
            continue
        if not any(k in d for k in ("storename", "address", "city")):
            continue
        store_id = to_int(d.get("storeid"))
        if store_id is None:
            continue

        # Sub-chain info may live on an ancestor (<SubChain><SubChainId>…<Stores><Store>)
        sub_id = d.get("subchainid")
        sub_name = d.get("subchainname")
        chain_name = d.get("chainname")
        for anc in el.iterancestors():
            ad = _children(anc)
            sub_id = sub_id or ad.get("subchainid")
            sub_name = sub_name or ad.get("subchainname")
            chain_name = chain_name or ad.get("chainname")

        yield StoreRecord(
            chain_id=d.get("chainid") or chain_id_default,
            store_id=store_id,
            store_name=clean_text(d.get("storename")),
            chain_name=clean_text(chain_name) or chain_name_default,
            subchain_id=clean_text(sub_id),
            subchain_name=clean_text(sub_name),
            address=clean_text(d.get("address")),
            city=clean_text(d.get("city")),
            zip_code=clean_text(d.get("zipcode")),
            store_type=clean_text(d.get("storetype")),
        )
