-- SCD2 integrity: periods of the same store × product must never overlap,
-- and there is at most one open period.
select a.chain_id, a.store_id, a.product_key, a.valid_from, b.valid_from as overlapping_from
from {{ ref('stg_price_history') }} a
join {{ ref('stg_price_history') }} b
  on a.chain_id = b.chain_id and a.store_id = b.store_id and a.product_key = b.product_key
 and a.valid_from < b.valid_from
 and (a.valid_to is null or a.valid_to > b.valid_from)
