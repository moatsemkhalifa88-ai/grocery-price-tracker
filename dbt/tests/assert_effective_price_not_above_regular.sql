select * from {{ ref('fct_current_price') }}
where effective_price > regular_price or effective_price <= 0
