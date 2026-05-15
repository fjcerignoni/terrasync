{{ config(
    materialized='external',
    location=staging_path('stg_incra_sigef_privado')
) }}

{{ clean_geometry(bronze_path('incra_sigef_privado'), source_epsg=4674) }}
