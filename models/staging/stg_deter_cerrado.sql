{{ config(
    materialized='external',
    location='data/staging/stg_deter_cerrado.parquet'
) }}

{{ clean_geometry('data/bronze/deter_cerrado/*.parquet', source_epsg=4674) }}
