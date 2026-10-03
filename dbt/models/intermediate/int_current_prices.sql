-- The price currently on the shelf in every tracked store
select
    h.chain_id,
    h.store_id,
    h.store_key,
    h.product_key,
    h.item_price as regular_price,
    h.unit_of_measure_price,
    h.valid_from as price_since
from {{ ref('stg_price_history') }} h
join {{ ref('stg_stores') }} s using (chain_id, store_id)
where h.is_current
  and s.is_tracked
