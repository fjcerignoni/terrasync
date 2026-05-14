{{ config(
    materialized='external',
    location='data/staging/stg_sicar.parquet'
) }}

{{ clean_geometry('data/bronze/sicar/*.parquet', source_epsg=4674) }}
