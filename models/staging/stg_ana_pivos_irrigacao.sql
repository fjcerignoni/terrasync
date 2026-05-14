{{ config(
    materialized='external',
    location='data/staging/stg_ana_pivos_irrigacao.parquet'
) }}

{{ clean_geometry('data/bronze/ana/pivos_irrigacao.parquet', source_epsg=4674) }}
