{{ config(
    materialized='external',
    location=staging_path('stg_prodes_pantanal')
) }}

{{ clean_geometry(bronze_path('prodes_pantanal'), source_epsg=4674) }}
