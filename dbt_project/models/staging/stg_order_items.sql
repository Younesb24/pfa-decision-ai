-- stg_order_items.sql
-- Staging model for Olist order items — one row per item in an order.
-- Same UNION pattern as stg_orders: legacy bronze.order_items + replay
-- bronze.order_items_live. Replay rows get the prefixed synthetic order_id
-- so the FK back to stg_orders holds.

with source as (
    select
        order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        price,
        freight_value,
        _loaded_at,
        _source_file,
        null::bigint as _replay_run_id,
        false        as _is_replay
    from {{ source('bronze', 'order_items') }}

    union all

    select
        'replay_' || _ingest_run_id::text || '_' || order_id  as order_id,
        order_item_id,
        product_id,
        seller_id,
        shipping_limit_date,
        price,
        freight_value,
        _ingested_at::timestamptz                              as _loaded_at,
        'bronze.order_items_live'                              as _source_file,
        _ingest_run_id                                         as _replay_run_id,
        true                                                   as _is_replay
    from {{ source('bronze', 'order_items_live') }}
),

cleaned as (
    select
        order_id,
        order_item_id::int                    as item_sequence,
        product_id,
        seller_id,
        shipping_limit_date::timestamp        as shipping_limit_at,

        -- Cast monetary values
        case when price != '' then price::numeric(10,2) else 0 end          as price,
        case when freight_value != '' then freight_value::numeric(10,2) else 0 end as freight_value,

        -- Computed: total item value
        (case when price != '' then price::numeric(10,2) else 0 end
         + case when freight_value != '' then freight_value::numeric(10,2) else 0 end
        ) as total_item_value,

        _loaded_at::timestamptz as _loaded_at,
        _source_file,
        _replay_run_id,
        _is_replay

    from source
    where order_id != ''
      and product_id != ''
)

select * from cleaned
