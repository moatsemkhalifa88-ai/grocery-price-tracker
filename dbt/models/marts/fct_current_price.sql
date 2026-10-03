-- Grain: tracked store × product. The main table behind search and comparisons.
select
    c.store_key,
    c.chain_id,
    c.store_id,
    c.product_key,
    c.regular_price,
    pr.promo_unit_price,
    pr.description                                   as promo_description,
    pr.end_at                                        as promo_ends_at,
    club.promo_unit_price                            as club_unit_price,
    least(c.regular_price, coalesce(pr.promo_unit_price, c.regular_price)) as effective_price,
    pr.promo_unit_price is not null                  as is_on_promo,
    round(100 * (1 - pr.promo_unit_price / c.regular_price), 1) as promo_discount_pct,
    c.unit_of_measure_price,
    c.price_since
from {{ ref('int_current_prices') }} c
left join {{ ref('int_active_promo_prices') }} pr
  on pr.chain_id = c.chain_id and pr.store_id = c.store_id
 and pr.product_key = c.product_key and not pr.is_club_only
left join {{ ref('int_active_promo_prices') }} club
  on club.chain_id = c.chain_id and club.store_id = c.store_id
 and club.product_key = c.product_key and club.is_club_only
