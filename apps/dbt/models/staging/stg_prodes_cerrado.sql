{{ config(
    materialized='external',
    location=staging_path('stg_prodes_cerrado')
) }}

{{ clean_geometry(bronze_path('prodes_cerrado'), source_epsg=4674) }}
