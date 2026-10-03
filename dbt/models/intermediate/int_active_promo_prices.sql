-- Best active promotion per store × product, as a price per single unit.
--
-- Since 2026 the reward sits on each promotion item (older files: on the
-- promotion). <DiscountedPrice> is the total for <MinQty> units — "2 for ₪30"
-- is 30 with MinQty 2, and a weighted "1.9 kg for ₪61.75" is per 1.9 kg —
-- so the unit price is DiscountedPrice / MinQty. Without a price we fall back
-- to the discount rate. <DiscountedPricePerMida> is per unit of MEASURE
-- (e.g. per 100 g), not per item, so it is not used here.
--
-- Left out on purpose: coupons, "spend over ₪X" deals, gifts (price 0) and
-- anything that would not be an actual discount.
with active as (
    select p.*
    from {{ ref('stg_promotions') }} p
    where (p.start_at is null or p.start_at <= (now() at time zone '{{ var("tz") }}'))
      and (p.end_at   is null or p.end_at   >= (now() at time zone '{{ var("tz") }}'))
      and not p.is_coupon
      and coalesce(p.min_purchase_amount, 0) = 0
),

priced as (
    select
        a.chain_id,
        a.store_id,
        a.store_key,
        i.product_key,
        a.promotion_id,
        a.description,
        a.is_club_only,
        coalesce(i.min_qty, a.min_qty, 1)                    as min_qty,
        a.end_at,
        c.regular_price,
        coalesce(i.discounted_price, a.discounted_price)     as discounted_price,
        coalesce(i.discount_pct, a.discount_pct)             as discount_pct
    from active a
    join {{ ref('stg_promotion_items') }} i using (chain_id, store_id, promotion_id)
    join {{ ref('int_current_prices') }} c
      on c.chain_id = a.chain_id and c.store_id = a.store_id and c.product_key = i.product_key
),

unit as (
    select
        *,
        case
            when discounted_price > 0 and min_qty >= 1 then discounted_price / min_qty
            when discounted_price > 0                  then discounted_price
            when discount_pct > 0 and discount_pct < 100
                then regular_price * (1 - discount_pct / 100.0)
        end as promo_unit_price
    from priced
),

ranked as (
    select *,
        row_number() over (
            partition by chain_id, store_id, product_key, is_club_only
            order by promo_unit_price, promotion_id
        ) as rn
    from unit
    where promo_unit_price > 0
      and promo_unit_price < regular_price          -- must actually be a discount
      and promo_unit_price >= regular_price * 0.2   -- and not a data error
)

select
    chain_id, store_id, store_key, product_key, is_club_only,
    promotion_id, description, min_qty, end_at,
    round(promo_unit_price::numeric, 2) as promo_unit_price
from ranked
where rn = 1
