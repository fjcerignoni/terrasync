{{ config(
    materialized='external',
    location='data/staging/stg_prodes_caatinga.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_caatinga/*.parquet', source_epsg=4674) }}
