{{ config(
    materialized='external',
    location=staging_path('stg_ibama')
) }}

{{ clean_geometry(bronze_path('ibama'), source_epsg=4674) }}
