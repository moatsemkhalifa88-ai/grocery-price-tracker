"""Build small transparency-format XML files for tests and demo data."""

from __future__ import annotations

from datetime import datetime
from xml.sax.saxutils import escape


def price_full_xml(chain_id: str, store_id: int, items: list[dict], updated: datetime) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<Root>",
        f"  <ChainId>{chain_id}</ChainId>",
        "  <SubChainId>001</SubChainId>",
        f"  <StoreId>{store_id:03d}</StoreId>",
        "  <BikoretNo>1</BikoretNo>",
        f'  <Items Count="{len(items)}">',
    ]
    for it in items:
        lines += [
            "    <Item>",
            f"      <PriceUpdateDate>{updated:%Y-%m-%d %H:%M:%S}</PriceUpdateDate>",
            f"      <ItemCode>{it['code']}</ItemCode>",
            f"      <ItemType>{it.get('type', 1)}</ItemType>",
            f"      <ItemName>{escape(it['name'])}</ItemName>",
            f"      <ManufacturerName>{escape(it.get('manufacturer', 'לא ידוע'))}</ManufacturerName>",
            "      <ManufactureCountry>ישראל</ManufactureCountry>",
            f"      <UnitQty>{it.get('unit_qty', 'יחידה')}</UnitQty>",
            f"      <Quantity>{it.get('quantity', 1)}</Quantity>",
            f"      <UnitOfMeasure>{it.get('uom', 'יחידה')}</UnitOfMeasure>",
            f"      <bIsWeighted>{1 if it.get('weighted') else 0}</bIsWeighted>",
            "      <QtyInPackage>1</QtyInPackage>",
            f"      <ItemPrice>{it['price']:.2f}</ItemPrice>",
            f"      <UnitOfMeasurePrice>{it['price']:.2f}</UnitOfMeasurePrice>",
            "      <AllowDiscount>1</AllowDiscount>",
            "      <ItemStatus>1</ItemStatus>",
            "    </Item>",
        ]
    lines += ["  </Items>", "</Root>"]
    return "\n".join(lines).encode("utf-8")


def stores_xml(chain_id: str, chain_name: str, stores: list[dict]) -> bytes:
    body = "".join(
        f"""
        <Store><StoreId>{s['id']:03d}</StoreId><BikoretNo>1</BikoretNo><StoreType>1</StoreType>
        <StoreName>{escape(s['name'])}</StoreName><Address>{escape(s.get('address', ''))}</Address>
        <City>{escape(s['city'])}</City><ZipCode>0</ZipCode></Store>"""
        for s in stores
    )
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Root><ChainId>{chain_id}</ChainId><ChainName>{escape(chain_name)}</ChainName>
  <SubChains><SubChain><SubChainId>001</SubChainId><SubChainName>{escape(chain_name)}</SubChainName>
    <Stores>{body}
    </Stores></SubChain></SubChains></Root>"""
    return xml.encode("utf-8")


def promo_full_xml(chain_id: str, store_id: int, promos: list[dict]) -> bytes:
    parts = []
    for p in promos:
        items = "".join(f"<Item><ItemCode>{c}</ItemCode><ItemType>1</ItemType></Item>" for c in p["codes"])
        parts.append(f"""
    <Promotion>
      <PromotionId>{p['id']}</PromotionId>
      <PromotionDescription>{escape(p['desc'])}</PromotionDescription>
      <PromotionUpdateDate>{p['start']:%Y-%m-%d} 08:00:00</PromotionUpdateDate>
      <PromotionStartDate>{p['start']:%Y-%m-%d}</PromotionStartDate><PromotionStartHour>00:00:00</PromotionStartHour>
      <PromotionEndDate>{p['end']:%Y-%m-%d}</PromotionEndDate><PromotionEndHour>23:59:00</PromotionEndHour>
      <RewardType>1</RewardType><MinQty>{p.get('min_qty', 1)}</MinQty>
      <DiscountedPrice>{p['price']:.2f}</DiscountedPrice>
      <PromotionItems Count="{len(p['codes'])}">{items}</PromotionItems>
      <Clubs><ClubId>{p.get('club', 0)}</ClubId></Clubs>
    </Promotion>""")
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<Root><ChainId>{chain_id}</ChainId><SubChainId>001</SubChainId><StoreId>{store_id:03d}</StoreId>
  <Promotions Count="{len(promos)}">{''.join(parts)}
  </Promotions></Root>"""
    return xml.encode("utf-8")
