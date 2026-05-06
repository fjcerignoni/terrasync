{{ config(
    materialized='external',
    location='data/silver/stg_ibama.parquet'
) }}

{{ clean_geometry('data/bronze/ibama/*.parquet') }}
