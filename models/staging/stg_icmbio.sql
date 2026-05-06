{{ config(
    materialized='external',
    location='data/silver/stg_icmbio.parquet'
) }}

{{ clean_geometry('data/bronze/icmbio/*.parquet') }}
