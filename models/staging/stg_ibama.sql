{{ config(
    materialized='external',
    location='data/staging/stg_ibama.parquet'
) }}

{{ clean_geometry('data/bronze/ibama/*.parquet', source_epsg=4674) }}
