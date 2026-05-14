{{ config(
    materialized='external',
    location='data/staging/stg_prodes_pampa.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_pampa/*.parquet', source_epsg=4674) }}
