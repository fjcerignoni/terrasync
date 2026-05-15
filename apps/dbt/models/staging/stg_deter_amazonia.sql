{{ config(
    materialized='external',
    location=staging_path('stg_deter_amazonia')
) }}

{{ clean_geometry(bronze_path('deter_amazonia'), source_epsg=4674) }}
