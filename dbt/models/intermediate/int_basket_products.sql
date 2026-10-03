-- The "basket": shared-barcode products sold by many chains, used for fair
-- chain-vs-chain comparisons and the price index.
with coverage as (
    select
        c.product_key,
        count(distinct c.chain_id) as n_chains,
        count(distinct c.store_key) as n_stores
    from {{ ref('int_current_prices') }} c
    join {{ ref('stg_products') }} p using (product_key)
    where p.is_barcode
    group by 1
),
total as (select count(distinct chain_id) as n from {{ ref('int_current_prices') }})

select
    product_key,
    n_chains,
    n_stores,
    n_chains = (select n from total) as in_all_chains
from coverage
where n_chains >= least({{ var('basket_min_chains') }}, (select n from total))
order by n_stores desc, product_key
limit {{ var('basket_size') }}
