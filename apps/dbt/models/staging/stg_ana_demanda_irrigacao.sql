{{ config(
    materialized='external',
    location=staging_path('stg_ana_demanda_irrigacao')
) }}

{{ clean_geometry(bronze_path('ana', 'ana_demanda_irrigacao.parquet'), source_epsg=4674) }}
