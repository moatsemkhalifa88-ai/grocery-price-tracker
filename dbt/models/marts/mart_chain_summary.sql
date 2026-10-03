-- Grain: chain. Headline numbers for the dashboard overview.
with latest_index as (
    select distinct on (chain_id) chain_id, day, price_index, basket_cost
    from {{ ref('mart_basket_index_daily') }}
    order by chain_id, day desc
),
changes as (
    select
        chain_id,
        count(*) filter (where direction = 'increase' and change_date > current_date - 30) as increases_30d,
        count(*) filter (where direction = 'decrease' and change_date > current_date - 30) as decreases_30d,
        round(avg(pct_change) filter (where change_date > current_date - 30), 2)        as avg_change_pct_30d
    from {{ ref('fct_price_changes') }}
    group by 1
),
promos as (
    select chain_id, count(*) filter (where is_on_promo) as items_on_promo,
           round(avg(promo_discount_pct), 1) as avg_promo_discount_pct,
           count(distinct product_key) as products_listed
    from {{ ref('fct_current_price') }}
    group by 1
)

select
    c.chain_id,
    c.chain_key,
    c.chain_name_he,
    c.chain_name_en,
    c.tracked_stores,
    p.products_listed,
    i.day                       as index_date,
    i.price_index,
    i.basket_cost,
    rank() over (order by i.basket_cost nulls last) as basket_rank,
    coalesce(ch.increases_30d, 0) as increases_30d,
    coalesce(ch.decreases_30d, 0) as decreases_30d,
    ch.avg_change_pct_30d,
    coalesce(p.items_on_promo, 0) as items_on_promo,
    p.avg_promo_discount_pct
from {{ ref('dim_chain') }} c
left join latest_index i using (chain_id)
left join changes ch using (chain_id)
left join promos p using (chain_id)
where c.tracked_stores > 0
