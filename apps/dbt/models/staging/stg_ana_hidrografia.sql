{{ config(
    materialized='external',
    location='data/staging/stg_ana_hidrografia.parquet'
) }}

{{ clean_geometry('data/bronze/ana/hidrografia.parquet', source_epsg=4674) }}
