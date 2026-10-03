select
    s.store_key,
    s.chain_id,
    c.chain_name_he,
    c.chain_name_en,
    s.store_id,
    s.store_name,
    s.subchain_name,
    s.address,
    s.city,
    s.is_tracked
from {{ ref('stg_stores') }} s
join {{ ref('stg_chains') }} c using (chain_id)
