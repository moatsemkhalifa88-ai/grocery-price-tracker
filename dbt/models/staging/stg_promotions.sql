select
    chain_id,
    store_id,
    chain_id || '-' || store_id  as store_key,
    promotion_id,
    description,
    start_at,
    end_at,
    reward_type,
    nullif(min_qty, 0)           as min_qty,
    discounted_price,
    -- some chains send 20% as 20, others as 2000 (hundredths)
    case when discount_rate > 100 then discount_rate / 100.0 else discount_rate end as discount_pct,
    min_purchase_amount,
    is_club_only,
    is_coupon,
    item_count
from {{ source('core', 'promotions') }}
