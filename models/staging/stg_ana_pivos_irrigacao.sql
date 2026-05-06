{{ config(
    materialized='external',
    location='data/silver/stg_ana_pivos_irrigacao.parquet'
) }}

{{ clean_geometry('data/bronze/ana/pivos_irrigacao.parquet') }}
