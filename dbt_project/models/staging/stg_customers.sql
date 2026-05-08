-- stg_customers.sql
-- Staging model for Olist customers
-- Note: customer_id is unique per ORDER, not per real customer
-- Use customer_unique_id for true customer-level analysis (RFM, churn)

with source as (
    select * from {{ source('bronze', 'customers') }}
),

cleaned as (
    select
        customer_id,
        customer_unique_id,
        customer_zip_code_prefix,
        lower(trim(customer_city))  as customer_city,
        upper(trim(customer_state)) as customer_state,

        -- Metadata
        _loaded_at::timestamptz as _loaded_at,
        _source_file

    from source
    where customer_id != ''
)

select * from cleaned
