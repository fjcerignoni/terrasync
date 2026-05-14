{{ config(
    materialized='external',
    location='data/staging/stg_deter_amazonia.parquet'
) }}

{{ clean_geometry('data/bronze/deter_amazonia/*.parquet', source_epsg=4674) }}
