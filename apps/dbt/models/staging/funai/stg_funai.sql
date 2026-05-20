{{ config(
    materialized='external',
    location=staging_path('stg_funai')
) }}

{{ clean_geometry(relation="SELECT * FROM " ~ source('rawdata_funai', 'funai'), source_epsg=4674) }}
