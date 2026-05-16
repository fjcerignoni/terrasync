{{ config(
    materialized='external',
    location=staging_path('stg_prodes_caatinga')
) }}

{{ clean_geometry(bronze_path('prodes_caatinga'), source_epsg=4674) }}
