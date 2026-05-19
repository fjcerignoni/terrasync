{{ config(
    materialized='external',
    location=staging_path('stg_incra_quilombolas')
) }}

{{ clean_geometry(rawdata_path('incra_quilombolas'), source_epsg=4674) }}
