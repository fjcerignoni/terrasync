{{ config(
    materialized='external',
    location='data/silver/stg_ana_hidrografia.parquet'
) }}

{{ clean_geometry('data/bronze/ana/hidrografia.parquet') }}
