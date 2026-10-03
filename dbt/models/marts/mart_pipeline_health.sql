-- Grain: chain × day. Data-quality / freshness view (also used in the web footer).
select
    chain_id,
    processed_at::date                               as day,
    count(*) filter (where status = 'loaded')        as files_loaded,
    count(*) filter (where status = 'failed')        as files_failed,
    count(*) filter (where status = 'skipped')       as files_skipped,
    sum(row_count) filter (where status = 'loaded')  as rows_parsed,
    max(published_at)                                as newest_file_at
from {{ source('ingest', 'file_log') }}
group by 1, 2
