-- stg_order_payments.sql
-- Staging model for Olist order payments — casts types, handles multi-payment orders.
-- UNIONs bronze.order_payments (legacy) with bronze.order_payments_live (replay).
-- The natural key in payments is (order_id, payment_sequential); we prefix
-- order_id with the replay run so cross-tick uniqueness holds.
-- Inspired by longNguyen010203/ECommerce-ELT-Pipeline staging patterns.

with source as (
    select
        order_id,
        payment_sequential,
        payment_type,
        payment_installments,
        payment_value,
        _loaded_at,
        _source_file,
        null::bigint as _replay_run_id,
        false        as _is_replay
    from {{ source('bronze', 'order_payments') }}

    union all

    select
        'replay_' || _ingest_run_id::text || '_' || order_id  as order_id,
        payment_sequential,
        payment_type,
        payment_installments,
        payment_value,
        _ingested_at::timestamptz                              as _loaded_at,
        'bronze.order_payments_live'                           as _source_file,
        _ingest_run_id                                         as _replay_run_id,
        true                                                   as _is_replay
    from {{ source('bronze', 'order_payments_live') }}
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
        _source_file,
        _replay_run_id,
        _is_replay

    from source
    where order_id != ''
      and payment_value != ''
)

select * from cleaned
