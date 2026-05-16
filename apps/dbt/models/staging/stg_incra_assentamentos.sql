{{ config(
    materialized='external',
    location=staging_path('stg_incra_assentamentos')
) }}

{{ clean_geometry(bronze_path('incra_assentamentos'), source_epsg=4674) }}
