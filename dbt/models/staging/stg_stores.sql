select
    chain_id,
    store_id,
    chain_id || '-' || store_id                       as store_key,
    coalesce(store_name, 'סניף ' || store_id)         as store_name,
    subchain_name,
    address,
    -- a few chains publish a numeric city code instead of a name
    case when city ~ '^[0-9]+$' then null else city end as city,
    is_tracked,
    first_seen_at,
    last_seen_at
from {{ source('core', 'stores') }}
