{{ config(
    materialized='external',
    location='data/silver/stg_prodes_cerrado.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_cerrado/*.parquet') }}
