{{ config(
    materialized='external',
    location='data/silver/stg_prodes_mata_atlantica.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_mata_atlantica/*.parquet') }}
