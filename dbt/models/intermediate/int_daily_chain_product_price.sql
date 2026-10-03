-- Average end-of-day shelf price per chain × basket product × day,
-- expanded from the SCD2 intervals over a date spine.
with bounds as (
    select min(valid_from)::date as first_day,
           (now() at time zone '{{ var("tz") }}')::date as last_day
    from {{ ref('stg_price_history') }}
),
days as (
    select generate_series(first_day, last_day, interval '1 day')::date as day
    from bounds
),
history as (
    select h.*
    from {{ ref('stg_price_history') }} h
    join {{ ref('int_basket_products') }} b using (product_key)
    join {{ ref('stg_stores') }} s using (chain_id, store_id)
    where s.is_tracked
)

select
    d.day,
    h.chain_id,
    h.product_key,
    avg(h.item_price)::numeric(10, 3) as avg_price,
    min(h.item_price)                 as min_price,
    count(*)                          as n_stores
from days d
join history h
  on h.valid_from < d.day + 1
 and (h.valid_to is null or h.valid_to >= d.day + 1)
group by 1, 2, 3
