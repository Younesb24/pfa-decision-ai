-- agg_seller_scorecard.sql
-- Composite seller risk score — KPI #5 from kpi_catalog.md
-- Components: late delivery rate (40%), avg review (30%), volume stability (20%), cancellation (10%)

{{ config(materialized='table') }}

with seller_orders as (
    select
        seller_id,
        count(distinct order_id)                                                    as total_orders,
        count(distinct case when order_status = 'delivered' then order_id end)      as delivered_orders,
        count(distinct case when is_late then order_id end)                         as late_orders,
        count(distinct case when order_status = 'canceled' then order_id end)       as canceled_orders,
        sum(total_item_value)                                                       as total_revenue,
        avg(total_item_value)                                                       as avg_order_value
    from {{ ref('fct_orders') }}
    group by seller_id
),

seller_reviews as (
    select
        fo.seller_id,
        avg(fr.review_score)       as avg_review_score,
        count(fr.review_id)        as review_count
    from {{ ref('fct_orders') }} fo
    inner join {{ ref('fct_reviews') }} fr on fo.order_id = fr.order_id
    group by fo.seller_id
),

-- Monthly order counts for volume stability (coefficient of variation)
seller_monthly as (
    select
        seller_id,
        date_trunc('month', order_purchase_at) as month,
        count(distinct order_id) as monthly_orders
    from {{ ref('fct_orders') }}
    group by 1, 2
),

seller_stability as (
    select
        seller_id,
        avg(monthly_orders) as avg_monthly_orders,
        case
            when avg(monthly_orders) > 0
            then stddev(monthly_orders) / avg(monthly_orders)
            else 0
        end as volume_cv  -- coefficient of variation (lower = more stable)
    from seller_monthly
    group by seller_id
),

scorecard as (
    select
        so.seller_id,
        so.total_orders,
        so.delivered_orders,
        so.late_orders,
        so.canceled_orders,
        so.total_revenue,
        so.avg_order_value,

        -- Late delivery rate
        case when so.delivered_orders > 0
            then round((so.late_orders::numeric / so.delivered_orders) * 100, 2)
            else 0
        end as late_delivery_rate,

        -- Review metrics
        coalesce(sr.avg_review_score, 0) as avg_review_score,
        coalesce(sr.review_count, 0) as review_count,

        -- Volume stability
        coalesce(ss.avg_monthly_orders, 0) as avg_monthly_orders,
        coalesce(ss.volume_cv, 0) as volume_cv,

        -- Cancellation rate
        case when so.total_orders > 0
            then round((so.canceled_orders::numeric / so.total_orders) * 100, 2)
            else 0
        end as cancellation_rate,

        -- COMPOSITE RISK SCORE (0-100, higher = riskier)
        -- Late delivery rate (40%) + inverted review (30%) + volume CV (20%) + cancellation (10%)
        round(
            (case when so.delivered_orders > 0
                then least((so.late_orders::numeric / so.delivered_orders) * 100, 100)
                else 0 end) * 0.40
            +
            (case when sr.avg_review_score is not null
                then (5.0 - sr.avg_review_score) / 4.0 * 100
                else 50 end) * 0.30
            +
            least(coalesce(ss.volume_cv, 0) * 100, 100) * 0.20
            +
            (case when so.total_orders > 0
                then least((so.canceled_orders::numeric / so.total_orders) * 100, 100)
                else 0 end) * 0.10
        , 2) as seller_risk_score

    from seller_orders so
    left join seller_reviews sr on so.seller_id = sr.seller_id
    left join seller_stability ss on so.seller_id = ss.seller_id
)

select * from scorecard
order by seller_risk_score desc
