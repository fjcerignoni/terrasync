{{ config(
    materialized='external',
    location='data/silver/stg_sicar.parquet'
) }}

{{ clean_geometry('data/bronze/sicar/*.parquet') }}
