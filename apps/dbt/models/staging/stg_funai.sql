{{ config(
    materialized='external',
    location=staging_path('stg_funai')
) }}

{{ clean_geometry(bronze_path('funai'), source_epsg=4674) }}
