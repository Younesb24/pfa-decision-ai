-- fct_reviews.sql
-- Review fact table — joined with order for customer context
-- Inspired by rtmagar fact_reviews pattern

{{ config(materialized='table') }}

with reviews as (
    select * from {{ ref('stg_order_reviews') }}
),

orders as (
    select * from {{ ref('stg_orders') }}
)

select
    r.review_id,
    r.order_id,
    o.customer_id,
    r.review_score,
    r.review_title,
    r.review_message,
    r.review_created_at,
    r.review_answered_at,
    to_char(r.review_created_at, 'YYYYMMDD')::integer as review_date_key,

    -- Computed: has comment flag (useful for NLP filtering)
    r.has_comment,

    -- Computed: NPS bucket (Promoter/Passive/Detractor)
    case
        when r.review_score >= 4 then 'promoter'
        when r.review_score = 3 then 'passive'
        else 'detractor'
    end as nps_category

from reviews r
inner join orders o on r.order_id = o.order_id
