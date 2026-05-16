{{ config(
    materialized='external',
    location=staging_path('stg_ana_hidrografia')
) }}

{{ clean_geometry(bronze_path('ana', 'ana_hidrografia.parquet'), source_epsg=4674) }}
