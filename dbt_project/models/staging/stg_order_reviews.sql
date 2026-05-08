-- stg_order_reviews.sql
-- Staging model for Olist order reviews

with source as (
    select * from {{ source('bronze', 'order_reviews') }}
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
        _source_file

    from source
    where review_id != ''
      and order_id != ''
)

select * from cleaned
