-- the first index value of every chain must be exactly 100
select chain_id, price_index
from (
    select chain_id, price_index, row_number() over (partition by chain_id order by day) as rn
    from {{ ref('mart_basket_index_daily') }}
) t
where rn = 1 and abs(price_index - 100) > 0.001
