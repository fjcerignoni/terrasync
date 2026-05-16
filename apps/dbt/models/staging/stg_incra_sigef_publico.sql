{{ config(
    materialized='external',
    location=staging_path('stg_incra_sigef_publico')
) }}

{{ clean_geometry(bronze_path('incra_sigef_publico'), source_epsg=4674) }}
