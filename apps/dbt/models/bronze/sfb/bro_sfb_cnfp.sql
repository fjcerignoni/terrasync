{{ config(
    materialized='external',
    location=bronze_path('sfb', 'cnfp'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sfb', glob='sfb_cnfp.parquet'), source_epsg=4674) }}