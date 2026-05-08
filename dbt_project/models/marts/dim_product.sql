-- dim_product.sql
-- Product dimension with EN category name and volume
-- Category translation already joined in stg_products

{{ config(materialized='table') }}

select
    row_number() over (order by product_id) as product_key,
    product_id,
    product_category_name,
    product_category_name_pt,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    product_volume_cm3
from {{ ref('stg_products') }}
