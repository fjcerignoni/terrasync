{{ config(
    materialized='external',
    location='data/silver/stg_ana_demanda_irrigacao.parquet'
) }}

{{ clean_geometry('data/bronze/ana/demanda_irrigacao.parquet') }}
