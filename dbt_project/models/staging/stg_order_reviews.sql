-- stg_order_reviews.sql
-- Staging model for Olist order reviews.
-- UNIONs bronze.order_reviews (legacy) with bronze.order_reviews_live (replay).
-- Replay rows get a prefixed review_id so uniqueness tests in fct_reviews
-- survive the multiple-tick scenario.
--
-- Note: order_id is NOT prefixed on replay rows, because the FK target in
-- stg_orders does the prefix on its side. This is consistent across all
-- replay-aware staging models — the prefix lives on the natural-key column
-- of the table being UNIONed, not on the FK.
-- TODO(day-3+): if we ever wire replay rows into fct_reviews->fct_orders
-- joins, we may need to prefix order_id here too. Leaving as-is until a
-- broken test forces it.

with source as (
    select
        review_id,
        order_id,
        review_score,
        review_comment_title,
        review_comment_message,
        review_creation_date,
        review_answer_timestamp,
        _loaded_at,
        _source_file,
        null::bigint as _replay_run_id,
        false        as _is_replay
    from {{ source('bronze', 'order_reviews') }}

    union all

    select
        'replay_' || _ingest_run_id::text || '_' || review_id  as review_id,
        order_id,
        review_score,
        review_comment_title,
        review_comment_message,
        review_creation_date,
        review_answer_timestamp,
        _ingested_at::timestamptz                                as _loaded_at,
        'bronze.order_reviews_live'                              as _source_file,
        _ingest_run_id                                           as _replay_run_id,
        true                                                     as _is_replay
    from {{ source('bronze', 'order_reviews_live') }}
),

cleaned as (
    select
        review_id,
        order_id,
        case when review_score != '' then review_score::int else null end as review_score,

        -- Keep text as-is for potential NLP later
        nullif(trim(review_comment_title), '')   as review_title,
        nullif(trim(review_comment_message), '') as review_message,

        -- Has the customer written a comment?
        case
            when trim(coalesce(review_comment_message, '')) != '' then true
            else false
        end as has_comment,

        case when review_creation_date != '' then review_creation_date::timestamp else null end as review_created_at,
        case when review_answer_timestamp != '' then review_answer_timestamp::timestamp else null end as review_answered_at,

        _loaded_at::timestamptz as _loaded_at,
        _source_file,
        _replay_run_id,
        _is_replay

    from source
    where review_id != ''
      and order_id != ''
)

select * from cleaned
