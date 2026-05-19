{{ config(
    materialized='external',
    location=bronze_path('sicar', 'ap'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_ap.parquet'), source_epsg=4674) }}