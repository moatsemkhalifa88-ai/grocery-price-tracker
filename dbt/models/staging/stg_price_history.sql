select
    h.chain_id,
    h.store_id,
    h.chain_id || '-' || h.store_id   as store_key,
    h.product_key,
    h.item_price,
    h.unit_of_measure_price,
    h.chain_item_name,
    h.valid_from,
    h.valid_to,
    h.valid_to is null                as is_current,
    h.source_file
from {{ source('core', 'price_history') }} h
