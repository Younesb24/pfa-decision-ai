-- stg_orders.sql
-- Staging model for Olist orders
-- Cleans types, filters invalid rows, adds computed columns

with source as (
    select * from {{ source('bronze', 'orders') }}
),

cleaned as (
    select
        order_id,
        customer_id,
        order_status,

        -- Cast timestamps (nullif handles empty strings from CSV)
        nullif(order_purchase_timestamp, '')::timestamp      as order_purchase_at,
        nullif(order_approved_at, '')::timestamp              as order_approved_at,
        nullif(order_delivered_carrier_date, '')::timestamp   as delivered_to_carrier_at,
        nullif(order_delivered_customer_date, '')::timestamp  as delivered_to_customer_at,
        nullif(order_estimated_delivery_date, '')::timestamp  as estimated_delivery_at,

        -- Computed: delivery delay in days (positive = late)
        case
            when order_delivered_customer_date != '' 
                 and order_estimated_delivery_date != ''
            then extract(epoch from (
                order_delivered_customer_date::timestamp 
                - order_estimated_delivery_date::timestamp
            )) / 86400.0
            else null
        end as delivery_delay_days,

        -- Computed: is_late flag
        case
            when order_delivered_customer_date != '' 
                 and order_estimated_delivery_date != ''
                 and order_delivered_customer_date::timestamp > order_estimated_delivery_date::timestamp
            then true
            else false
        end as is_late,

        -- Metadata
        _loaded_at::timestamptz as _loaded_at,
        _source_file

    from source
    where order_id != ''
      and order_purchase_timestamp != ''
)

select * from cleaned
