{{ config(
    materialized='external',
    location=bronze_path('sicar', 'ac'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_ac.parquet'), source_epsg=4674) }}