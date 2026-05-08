-- stg_sellers.sql
-- Staging model for Olist sellers
-- Normalizes city names (lowercase, trim)

with source as (
    select * from {{ source('bronze', 'sellers') }}
),

cleaned as (
    select
        seller_id,
        seller_zip_code_prefix,
        lower(trim(seller_city))  as seller_city,
        upper(trim(seller_state)) as seller_state,

        -- Metadata
        _loaded_at::timestamptz as _loaded_at,
        _source_file

    from source
    where seller_id != ''
)

select * from cleaned
