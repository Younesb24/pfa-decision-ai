-- dim_date.sql
-- Date dimension (date spine from orders data range)
-- Materialized as table for fast joins
-- Adapted from Kimball star schema convention

{{ config(materialized='table') }}

with date_spine as (
    select
        generate_series(
            '2016-09-01'::date,
            '2018-12-31'::date,
            '1 day'::interval
        )::date as full_date
),

dates as (
    select
        to_char(full_date, 'YYYYMMDD')::integer   as date_key,
        full_date,
        extract(year from full_date)::integer      as year,
        extract(month from full_date)::integer     as month,
        extract(quarter from full_date)::integer   as quarter,
        extract(week from full_date)::integer      as week_of_year,
        extract(dow from full_date)::integer       as day_of_week,
        to_char(full_date, 'Day')                  as day_name,
        to_char(full_date, 'Month')                as month_name,
        extract(day from full_date)::integer       as day_of_month,
        case when extract(dow from full_date) in (0, 6) then true else false end as is_weekend,
        -- Brazilian holidays (simplified: major ones)
        case when (extract(month from full_date) = 1 and extract(day from full_date) = 1)    -- Ano Novo
             or (extract(month from full_date) = 4 and extract(day from full_date) = 21)     -- Tiradentes
             or (extract(month from full_date) = 5 and extract(day from full_date) = 1)      -- Dia do Trabalho
             or (extract(month from full_date) = 9 and extract(day from full_date) = 7)      -- Independência
             or (extract(month from full_date) = 10 and extract(day from full_date) = 12)    -- N.S. Aparecida
             or (extract(month from full_date) = 11 and extract(day from full_date) = 2)     -- Finados
             or (extract(month from full_date) = 11 and extract(day from full_date) = 15)    -- Proclamação República
             or (extract(month from full_date) = 12 and extract(day from full_date) = 25)    -- Natal
             then true else false
        end as is_brazilian_holiday

    from date_spine
)

select * from dates
