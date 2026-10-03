select
    chain_id,
    store_id,
    chain_id || '-' || store_id as store_key,
    promotion_id,
    product_key,
    reward_type,
    nullif(min_qty, 0)          as min_qty,
    discounted_price,
    price_per_unit,
    case when discount_rate > 100 then discount_rate / 100.0 else discount_rate end as discount_pct
from {{ source('core', 'promotion_items') }}
