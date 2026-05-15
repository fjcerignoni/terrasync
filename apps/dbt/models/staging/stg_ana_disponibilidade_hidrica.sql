{{ config(
    materialized='external',
    location=staging_path('stg_ana_disponibilidade_hidrica')
) }}

{{ clean_geometry(bronze_path('ana', 'disponibilidade_hidrica.parquet'), source_epsg=4674) }}
