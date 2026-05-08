-- dim_customer.sql
-- Customer dimension — uses customer_unique_id as true grain
-- Adapted from rtmagar/ecommerce-elt-pipeline dim_customers pattern

{{ config(materialized='table') }}

with customers as (
    select * from {{ ref('stg_customers') }}
),

-- Deduplicate: pick latest record per unique customer
ranked as (
    select
        customer_unique_id,
        customer_zip_code_prefix,
        customer_city,
        customer_state,
        row_number() over (
            partition by customer_unique_id
            order by _loaded_at desc
        ) as rn
    from customers
)

select
    row_number() over (order by customer_unique_id) as customer_key,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
from ranked
where rn = 1
