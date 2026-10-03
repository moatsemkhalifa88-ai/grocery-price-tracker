-- Grain: tracked store. Cost of the shared basket at today's effective prices.
with common as (
    select product_key from {{ ref('int_basket_products') }} where in_all_chains
)
select
    s.store_key,
    s.chain_id,
    s.chain_name_he,
    s.store_name,
    s.city,
    count(f.product_key)                                    as basket_items_available,
    (select count(*) from common)                           as basket_items_total,
    round(100.0 * count(f.product_key) / nullif((select count(*) from common), 0), 1) as coverage_pct,
    sum(f.effective_price)                                  as basket_cost,
    sum(f.regular_price)                                    as basket_cost_regular,
    count(*) filter (where f.is_on_promo)                   as items_on_promo,
    rank() over (order by sum(f.effective_price) / nullif(count(f.product_key), 0)) as value_rank
from {{ ref('dim_store') }} s
left join {{ ref('fct_current_price') }} f
  on f.store_key = s.store_key and f.product_key in (select product_key from common)
where s.is_tracked
group by 1, 2, 3, 4, 5
