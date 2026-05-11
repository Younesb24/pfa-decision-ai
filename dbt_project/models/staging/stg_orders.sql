-- stg_orders.sql
-- Staging model for Olist orders.
-- UNION the legacy bronze.orders (one-shot CSV load) with bronze.orders_live
-- (replay simulator output) so Gold sees a continuously growing dataset.
--
-- Replay rows get a synthetic prefix on order_id ("replay_<run_id>_<order_id>")
-- so the uniqueness constraints in fct_orders still hold when the same
-- historical order is materialised multiple times across replay ticks.

with source as (
    select
        order_id,
        customer_id,
        order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        _loaded_at,
        _source_file,
        null::bigint as _replay_run_id,
        false        as _is_replay
    from {{ source('bronze', 'orders') }}

    union all

    select
        'replay_' || _ingest_run_id::text || '_' || order_id  as order_id,
        customer_id,
        order_status,
        order_purchase_timestamp,
        order_approved_at,
        order_delivered_carrier_date,
        order_delivered_customer_date,
        order_estimated_delivery_date,
        _ingested_at::timestamptz                              as _loaded_at,
        'bronze.orders_live'                                   as _source_file,
        _ingest_run_id                                         as _replay_run_id,
        true                                                   as _is_replay
    from {{ source('bronze', 'orders_live') }}
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
        _source_file,
        _replay_run_id,
        _is_replay

    from source
    where order_id != ''
      and order_purchase_timestamp != ''
)

select * from cleaned
