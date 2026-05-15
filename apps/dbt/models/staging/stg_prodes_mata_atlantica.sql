{{ config(
    materialized='external',
    location=staging_path('stg_prodes_mata_atlantica')
) }}

{{ clean_geometry(bronze_path('prodes_mata_atlantica'), source_epsg=4674) }}
