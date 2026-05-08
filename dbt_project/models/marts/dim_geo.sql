-- dim_geo.sql
-- Geography dimension — deduplicated geolocation with surrogate key

{{ config(materialized='table') }}

select
    row_number() over (order by zip_code_prefix, city) as geo_key,
    zip_code_prefix,
    city,
    state,
    latitude,
    longitude
from {{ ref('stg_geolocation') }}
