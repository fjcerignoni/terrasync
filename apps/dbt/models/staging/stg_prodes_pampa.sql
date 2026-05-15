{{ config(
    materialized='external',
    location=staging_path('stg_prodes_pampa')
) }}

{{ clean_geometry(bronze_path('prodes_pampa'), source_epsg=4674) }}
