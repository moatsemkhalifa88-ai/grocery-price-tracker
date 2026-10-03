with bounds as (
    select coalesce(min(valid_from)::date, current_date) as first_day
    from {{ ref('stg_price_history') }}
)
select
    d::date                                   as date_day,
    extract(isodow from d)::int               as iso_day_of_week,
    (array['שני','שלישי','רביעי','חמישי','שישי','שבת','ראשון'])[extract(isodow from d)::int] as day_name_he,
    to_char(d, 'Dy')                          as day_name_en,
    date_trunc('week', d)::date               as week_start,
    date_trunc('month', d)::date              as month_start,
    to_char(d, 'YYYY-MM')                     as year_month,
    extract(isodow from d) in (5, 6)          as is_weekend_il
from bounds, generate_series(first_day, (now() at time zone '{{ var("tz") }}')::date + 30, interval '1 day') d
