-- Grain: chain × day. Feeds the "price changes over time" chart.
select
    chain_id,
    change_date,
    count(*) filter (where direction = 'increase') as n_increases,
    count(*) filter (where direction = 'decrease') as n_decreases,
    round(avg(pct_change), 2)                      as avg_pct_change,
    round(avg(pct_change) filter (where direction = 'increase'), 2) as avg_increase_pct
from {{ ref('fct_price_changes') }}
group by 1, 2
