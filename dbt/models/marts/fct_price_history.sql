{{ config(materialized='view') }}
-- Full SCD2 history for tracked stores (a view: the web product page reads it
-- for one product at a time, so nothing is duplicated on disk).
select
    h.store_key,
    h.chain_id,
    h.store_id,
    h.product_key,
    h.item_price,
    h.valid_from,
    h.valid_to,
    h.is_current
from {{ ref('stg_price_history') }} h
join {{ ref('stg_stores') }} s using (chain_id, store_id)
where s.is_tracked
