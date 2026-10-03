select
    product_key,
    item_code,
    is_barcode,
    owner_chain_id,
    coalesce(item_name, item_code)  as product_name,
    manufacturer_name,
    manufacture_country,
    quantity,
    unit_qty,
    unit_of_measure,
    coalesce(is_weighted, false)    as is_weighted,
    first_seen_at,
    last_seen_at
from {{ source('core', 'products') }}
