-- stg_order_payments.sql
-- Staging model for Olist order payments
-- Casts types, handles multi-payment orders
-- Inspired by longNguyen010203/ECommerce-ELT-Pipeline staging patterns

with source as (
    select * from {{ source('bronze', 'order_payments') }}
),

cleaned as (
    select
        order_id,
        payment_sequential::integer          as payment_sequential,
        payment_type,
        payment_installments::integer        as payment_installments,
        payment_value::numeric(10, 2)        as payment_value,

        -- Metadata
        _loaded_at::timestamptz as _loaded_at,
        _source_file

    from source
    where order_id != ''
      and payment_value != ''
)

select * from cleaned
