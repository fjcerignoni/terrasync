{{ config(
    materialized='external',
    location='data/staging/stg_funai.parquet'
) }}

{{ clean_geometry('data/bronze/funai/*.parquet', source_epsg=4674) }}
