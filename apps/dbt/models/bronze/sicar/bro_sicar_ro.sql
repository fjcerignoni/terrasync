{{ config(
    materialized='external',
    location=bronze_path('sicar', 'ro'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_ro.parquet'), source_epsg=4674) }}