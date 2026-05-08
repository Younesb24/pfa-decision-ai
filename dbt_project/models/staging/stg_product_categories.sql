-- stg_product_categories.sql
-- Staging model for category name translation (PT → EN)
-- 71 categories total

with source as (
    select * from {{ source('bronze', 'product_category_name_translation') }}
),

cleaned as (
    select
        product_category_name           as category_name_pt,
        product_category_name_english   as category_name_en,

        -- Metadata
        _loaded_at::timestamptz as _loaded_at,
        _source_file

    from source
    where product_category_name != ''
)

select * from cleaned
