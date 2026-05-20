{{ config(
    materialized='external',
    location=staging_path('stg_sfb_cnfp')
) }}

{{ clean_geometry(relation="SELECT * FROM " ~ source('rawdata_sfb', 'sfb_cnfp'), source_epsg=4674) }}
