-- agg_daily_ops_kpi.sql
-- Pre-computed daily operational KPIs for dashboard + LLM narration
-- Source: kpi_catalog.md (OTIF, AOV, Cancellation Rate)
-- Inspired by longNguyen010203 sales_values_by_* aggregation pattern

{{ config(materialized='table') }}

with daily_orders as (
    select
        order_purchase_at::date                          as order_date,
        to_char(order_purchase_at, 'YYYYMMDD')::integer  as date_key,

        -- Volume
        count(distinct order_id)                         as total_orders,
        count(*)                                         as total_items,

        -- Revenue
        sum(price)                                       as total_revenue,
        sum(freight_value)                               as total_freight,
        sum(total_item_value)                            as total_gmv,
        avg(total_item_value)                            as avg_item_value,

        -- OTIF (On-Time In-Full) — KPI #1
        count(distinct case when order_status = 'delivered' then order_id end) as delivered_orders,
        count(distinct case when order_status = 'delivered' and not is_late then order_id end) as on_time_orders,
        count(distinct case when order_status = 'canceled' then order_id end) as canceled_orders,

        -- Delivery metrics
        avg(case when delivery_delay_days is not null then delivery_delay_days end) as avg_delivery_delay_days,
        avg(case when processing_time_days is not null then processing_time_days end) as avg_processing_time_days,
        avg(case when shipping_time_days is not null then shipping_time_days end) as avg_shipping_time_days,
        avg(case when total_lead_time_days is not null then total_lead_time_days end) as avg_lead_time_days,

        -- Unique actors
        count(distinct seller_id)                        as active_sellers,
        count(distinct customer_unique_id)               as unique_customers

    from {{ ref('fct_orders') }}
    group by 1, 2
),

with_kpis as (
    select
        *,

        -- AOV (Average Order Value) — KPI #2
        case when total_orders > 0
            then total_gmv / total_orders
            else 0
        end as aov,

        -- OTIF Rate — KPI #1
        case when delivered_orders > 0
            then round((on_time_orders::numeric / delivered_orders) * 100, 2)
            else null
        end as otif_rate,

        -- Cancellation Rate — KPI #4
        case when total_orders > 0
            then round((canceled_orders::numeric / total_orders) * 100, 2)
            else 0
        end as cancellation_rate

    from daily_orders
)

select * from with_kpis
order by order_date
