{{ config(
    materialized='external',
    location=staging_path('stg_icmbio')
) }}

{{ clean_geometry(bronze_path('icmbio'), source_epsg=4674) }}
