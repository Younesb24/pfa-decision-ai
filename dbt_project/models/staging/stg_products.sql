-- stg_products.sql
-- Staging model for Olist products
-- Casts dimensions to numeric, joins with category translation
-- Note: original dataset has typo "lenght" — we rename to "length" in silver
-- Inspired by longNguyen010203/ECommerce-ELT-Pipeline + rismawidiya/Final-Project-Olist feature eng

with source as (
    select * from {{ source('bronze', 'products') }}
),

translation as (
    select * from {{ source('bronze', 'product_category_name_translation') }}
),

cleaned as (
    select
        p.product_id,
        p.product_category_name                               as product_category_name_pt,
        t.product_category_name_english                       as product_category_name,
        nullif(p.product_name_lenght, '')::integer             as product_name_length,
        nullif(p.product_description_lenght, '')::integer      as product_description_length,
        nullif(p.product_photos_qty, '')::integer              as product_photos_qty,
        nullif(p.product_weight_g, '')::numeric                as product_weight_g,
        nullif(p.product_length_cm, '')::numeric               as product_length_cm,
        nullif(p.product_height_cm, '')::numeric               as product_height_cm,
        nullif(p.product_width_cm, '')::numeric                as product_width_cm,

        -- Computed: volume in cm3 (used as ML feature for late delivery prediction)
        case
            when p.product_length_cm != '' and p.product_height_cm != '' and p.product_width_cm != ''
            then (p.product_length_cm::numeric * p.product_height_cm::numeric * p.product_width_cm::numeric)
            else null
        end as product_volume_cm3,

        -- Metadata
        p._loaded_at::timestamptz as _loaded_at,
        p._source_file

    from source p
    left join translation t
        on p.product_category_name = t.product_category_name
    where p.product_id != ''
)

select * from cleaned
