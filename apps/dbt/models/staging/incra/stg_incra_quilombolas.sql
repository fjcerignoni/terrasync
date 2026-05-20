{{ config(
    materialized='external',
    location=staging_path('stg_incra_quilombolas')
) }}

{{ clean_geometry(relation="SELECT * FROM " ~ source('rawdata_incra', 'incra_quilombolas'), source_epsg=4674) }}
