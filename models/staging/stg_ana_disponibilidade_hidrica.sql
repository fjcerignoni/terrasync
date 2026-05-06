{{ config(
    materialized='external',
    location='data/silver/stg_ana_disponibilidade_hidrica.parquet'
) }}

{{ clean_geometry('data/bronze/ana/disponibilidade_hidrica.parquet') }}
