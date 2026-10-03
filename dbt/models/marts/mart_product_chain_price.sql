-- Grain: barcode product × chain. "Where is it cheapest right now?"
with by_chain as (
    select
        f.product_key,
        f.chain_id,
        min(f.effective_price)        as min_price,
        round(avg(f.effective_price), 2) as avg_price,
        max(f.effective_price)        as max_price,
        count(*)                      as n_stores,
        bool_or(f.is_on_promo)        as any_promo
    from {{ ref('fct_current_price') }} f
    join {{ ref('stg_products') }} p using (product_key)
    where p.is_barcode
    group by 1, 2
),
ranked as (
    select
        b.*,
        count(*) over (partition by product_key)            as n_chains,
        min(min_price) over (partition by product_key)      as best_price,
        rank() over (partition by product_key order by min_price) as price_rank
    from by_chain b
)

select
    r.product_key,
    r.chain_id,
    r.min_price,
    r.avg_price,
    r.max_price,
    r.n_stores,
    r.any_promo,
    r.n_chains,
    r.best_price,
    r.price_rank,
    r.price_rank = 1                                            as is_cheapest,
    round(100.0 * (r.min_price - r.best_price) / r.best_price, 1) as pct_above_best
from ranked r
