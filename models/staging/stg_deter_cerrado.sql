{{ config(
    materialized='external',
    location='data/silver/stg_deter_cerrado.parquet'
) }}

{{ clean_geometry('data/bronze/deter_cerrado/*.parquet') }}
