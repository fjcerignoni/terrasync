{{ config(
    materialized='external',
    location=staging_path('stg_incra_assentamentos')
) }}

{{ clean_geometry(relation="SELECT * FROM " ~ source('rawdata_incra', 'incra_assentamentos'), source_epsg=4674) }}
