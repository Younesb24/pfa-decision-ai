-- stg_geolocation.sql
-- Staging model for Olist geolocation
-- IMPORTANT: source has multiple rows per zip code (different lat/lng)
-- We deduplicate by taking the average lat/lng per zip+city+state
-- This matches the approach in tahatuzel/olist-batch-processing-etl

with source as (
    select * from {{ source('bronze', 'geolocation') }}
),

deduped as (
    select
        geolocation_zip_code_prefix         as zip_code_prefix,
        lower(trim(geolocation_city))       as city,
        upper(trim(geolocation_state))      as state,
        avg(geolocation_lat::numeric)       as latitude,
        avg(geolocation_lng::numeric)       as longitude,
        count(*)                            as geo_point_count

    from source
    where geolocation_zip_code_prefix != ''
      and geolocation_lat != ''
      and geolocation_lng != ''
    group by 1, 2, 3
)

select * from deduped
