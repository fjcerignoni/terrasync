{{ config(
    materialized='external',
    location='data/staging/stg_ana_demanda_irrigacao.parquet'
) }}

{{ clean_geometry('data/bronze/ana/demanda_irrigacao.parquet', source_epsg=4674) }}
