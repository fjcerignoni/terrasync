{{ config(
    materialized='external',
    location=staging_path('stg_prodes_amazonia')
) }}

{{ clean_geometry(bronze_path('prodes_amazonia'), source_epsg=4674) }}
