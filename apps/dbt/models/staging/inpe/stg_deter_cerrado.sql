{{ config(
    materialized='external',
    location=staging_path('stg_deter_cerrado')
) }}

{{ clean_geometry(relation="SELECT * FROM " ~ source('rawdata_inpe', 'deter_cerrado'), source_epsg=4674) }}
