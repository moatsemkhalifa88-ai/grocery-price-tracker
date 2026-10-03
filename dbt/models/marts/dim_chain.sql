select
    c.chain_id,
    c.chain_key,
    c.chain_name_he,
    c.chain_name_en,
    count(s.store_id) filter (where s.is_tracked) as tracked_stores
from {{ ref('stg_chains') }} c
left join {{ ref('stg_stores') }} s using (chain_id)
group by 1, 2, 3, 4
