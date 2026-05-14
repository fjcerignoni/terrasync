{{ config(
    materialized='external',
    location='data/staging/stg_prodes_amazonia.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_amazonia/*.parquet', source_epsg=4674) }}
