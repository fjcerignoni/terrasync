{{ config(
    materialized='external',
    location='data/staging/stg_prodes_cerrado.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_cerrado/*.parquet', source_epsg=4674) }}
