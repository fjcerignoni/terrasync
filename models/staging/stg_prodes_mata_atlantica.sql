{{ config(
    materialized='external',
    location='data/staging/stg_prodes_mata_atlantica.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_mata_atlantica/*.parquet', source_epsg=4674) }}
