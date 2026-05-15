{{ config(
    materialized='external',
    location=staging_path('stg_deter_cerrado')
) }}

{{ clean_geometry(bronze_path('deter_cerrado'), source_epsg=4674) }}
