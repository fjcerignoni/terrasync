{{ config(
    materialized='external',
    location='data/staging/stg_sfb_concessoes.parquet'
) }}

{{ clean_geometry('data/bronze/sfb/concessoes.parquet', source_epsg=4674) }}
