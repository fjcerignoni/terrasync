{{ config(
    materialized='external',
    location=bronze_path('sicar', 'rr'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_rr.parquet'), source_epsg=4674) }}