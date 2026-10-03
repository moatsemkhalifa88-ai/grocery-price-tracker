-- Grain: chain × day.
--   price_index : Jevons index (geometric mean of price relatives, base = 100 on
--                 each product's first observed day) — the same elementary index
--                 the Central Bureau of Statistics uses inside the CPI.
--   basket_cost : sum of average shelf prices over products that EVERY chain
--                 sold that day, so the totals are directly comparable.
with daily as (
    select
        d.*,
        first_value(d.avg_price) over (partition by d.chain_id, d.product_key order by d.day) as base_price,
        count(*) over (partition by d.product_key, d.day)  as chains_selling
    from {{ ref('int_daily_chain_product_price') }} d
),
n_chains as (select count(distinct chain_id) as n from daily)

select
    d.chain_id,
    d.day,
    round((100 * exp(avg(ln(d.avg_price / d.base_price))))::numeric, 3)          as price_index,
    count(*)                                                                    as n_products,
    round(sum(d.avg_price) filter (where d.chains_selling = (select n from n_chains)), 2) as basket_cost,
    count(*) filter (where d.chains_selling = (select n from n_chains))          as basket_products
from daily d
group by 1, 2
