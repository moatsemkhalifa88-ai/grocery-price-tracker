select
    chain_id,
    chain_key,
    name_he  as chain_name_he,
    name_en  as chain_name_en
from {{ source('core', 'chains') }}
