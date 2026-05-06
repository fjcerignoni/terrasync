{{ config(
    materialized='external',
    location='data/silver/stg_funai.parquet'
) }}

{{ clean_geometry('data/bronze/funai/*.parquet') }}
