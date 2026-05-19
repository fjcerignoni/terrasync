{{ config(
    materialized='external',
    location=bronze_path('sicar', 'se'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_se.parquet'), source_epsg=4674) }}