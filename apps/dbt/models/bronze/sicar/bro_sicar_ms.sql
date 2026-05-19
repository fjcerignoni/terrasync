{{ config(
    materialized='external',
    location=bronze_path('sicar', 'ms'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_ms.parquet'), source_epsg=4674) }}