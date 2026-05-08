-- stg_order_items.sql
-- Staging model for Olist order items
-- One row per item in an order

with source as (
    select * from {{ source('bronze', 'order_items') }}
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
        _source_file

    from source
    where order_id != ''
      and product_id != ''
)

select * from cleaned
