{{ config(
    materialized='external',
    location=bronze_path('sicar', 'am'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_am.parquet'), source_epsg=4674) }}