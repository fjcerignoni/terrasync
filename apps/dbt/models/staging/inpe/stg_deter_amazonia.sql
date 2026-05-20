{{ config(
    materialized='external',
    location=staging_path('stg_deter_amazonia')
) }}

{{ clean_geometry(relation="SELECT * FROM " ~ source('rawdata_inpe', 'deter_amazonia'), source_epsg=4674) }}
