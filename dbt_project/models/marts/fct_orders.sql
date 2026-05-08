-- fct_orders.sql
-- Core fact table — grain = one row per order item
-- Joins orders + items + payments (aggregated) for complete order economics
-- Inspired by rtmagar fact_sales.sql pattern, enriched with delivery KPIs
-- Ref: kpi_catalog.md (OTIF, AOV, Cancellation Rate, Delivery Delay)

{{ config(materialized='table') }}

with orders as (
    select * from {{ ref('stg_orders') }}
),

items as (
    select * from {{ ref('stg_order_items') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

-- Aggregate payments per order (one order can have multiple payment methods)
payments_agg as (
    select
        order_id,
        count(*)                                    as payment_count,
        sum(payment_value)                          as total_payment_value,
        max(payment_installments)                   as max_installments,
        string_agg(distinct payment_type, ', ')     as payment_types
    from {{ ref('stg_order_payments') }}
    group by order_id
),

-- Join dim keys
dim_cust as (
    select customer_key, customer_unique_id from {{ ref('dim_customer') }}
),

dim_sell as (
    select seller_key, seller_id from {{ ref('dim_seller') }}
),

dim_prod as (
    select product_key, product_id from {{ ref('dim_product') }}
)

select
    -- IDs
    i.order_id,
    i.item_sequence                                         as order_item_id,

    -- Dimension keys (for star schema joins)
    dc.customer_key,
    ds.seller_key,
    dp.product_key,
    case when o.order_purchase_at is not null
        then to_char(o.order_purchase_at, 'YYYYMMDD')::integer
        else null end                                           as purchase_date_key,
    case when o.delivered_to_customer_at is not null
        then to_char(o.delivered_to_customer_at, 'YYYYMMDD')::integer
        else null end                                           as delivery_date_key,

    -- Natural keys (for direct queries)
    o.customer_id,
    c.customer_unique_id,
    i.product_id,
    i.seller_id,

    -- Order status
    o.order_status,

    -- Timestamps
    o.order_purchase_at,
    o.order_approved_at,
    o.delivered_to_carrier_at,
    o.delivered_to_customer_at,
    o.estimated_delivery_at,

    -- Financials (BRL)
    i.price,
    i.freight_value,
    (i.price + i.freight_value)                             as total_item_value,
    pa.total_payment_value                                  as order_total_payment,
    pa.payment_count,
    pa.max_installments,
    pa.payment_types,

    -- Delivery KPIs (from stg_orders computed columns)
    o.delivery_delay_days,
    o.is_late,

    -- Computed: processing time (purchase → carrier handoff) in days
    case
        when o.delivered_to_carrier_at is not null and o.order_purchase_at is not null
        then extract(epoch from (o.delivered_to_carrier_at - o.order_purchase_at)) / 86400.0
        else null
    end as processing_time_days,

    -- Computed: shipping time (carrier → customer) in days
    case
        when o.delivered_to_customer_at is not null and o.delivered_to_carrier_at is not null
        then extract(epoch from (o.delivered_to_customer_at - o.delivered_to_carrier_at)) / 86400.0
        else null
    end as shipping_time_days,

    -- Computed: total lead time (purchase → delivery) in days
    case
        when o.delivered_to_customer_at is not null and o.order_purchase_at is not null
        then extract(epoch from (o.delivered_to_customer_at - o.order_purchase_at)) / 86400.0
        else null
    end as total_lead_time_days

from items i
inner join orders o on i.order_id = o.order_id
inner join customers c on o.customer_id = c.customer_id
left join payments_agg pa on o.order_id = pa.order_id
left join dim_cust dc on c.customer_unique_id = dc.customer_unique_id
left join dim_sell ds on i.seller_id = ds.seller_id
left join dim_prod dp on i.product_id = dp.product_id
