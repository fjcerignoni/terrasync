{{ config(
    materialized='external',
    location=bronze_path('sicar', 'pe'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_pe.parquet'), source_epsg=4674) }}