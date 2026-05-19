{{ config(
    materialized='external',
    location=bronze_path('sicar', 'al'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_al.parquet'), source_epsg=4674) }}