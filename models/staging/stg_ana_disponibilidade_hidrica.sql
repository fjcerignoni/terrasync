{{ config(
    materialized='external',
    location='data/staging/stg_ana_disponibilidade_hidrica.parquet'
) }}

{{ clean_geometry('data/bronze/ana/disponibilidade_hidrica.parquet', source_epsg=4674) }}
