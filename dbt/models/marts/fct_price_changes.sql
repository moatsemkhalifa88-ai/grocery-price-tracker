-- Grain: one shelf-price change in one store. First appearances are not changes.
with ordered as (
    select
        h.*,
        lag(h.item_price) over w as previous_price,
        lag(h.valid_to)   over w as previous_valid_to
    from {{ ref('stg_price_history') }} h
    window w as (partition by h.chain_id, h.store_id, h.product_key order by h.valid_from)
)

select
    o.store_key,
    o.chain_id,
    o.store_id,
    o.product_key,
    o.valid_from::date                                        as change_date,
    o.valid_from                                              as changed_at,
    o.previous_price,
    o.item_price                                              as new_price,
    o.item_price - o.previous_price                           as price_delta,
    round(100.0 * (o.item_price - o.previous_price) / o.previous_price, 2) as pct_change,
    case when o.item_price > o.previous_price then 'increase' else 'decrease' end as direction
from ordered o
join {{ ref('stg_stores') }} s using (chain_id, store_id)
where o.previous_price is not null
  and o.previous_valid_to = o.valid_from        -- a real change, not a re-listing after a gap
  and o.item_price <> o.previous_price
  and s.is_tracked
