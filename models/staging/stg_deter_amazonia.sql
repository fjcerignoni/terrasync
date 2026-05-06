{{ config(
    materialized='external',
    location='data/silver/stg_deter_amazonia.parquet'
) }}

{{ clean_geometry('data/bronze/deter_amazonia/*.parquet') }}
