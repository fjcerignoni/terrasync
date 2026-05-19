{{ config(
    materialized='external',
    location=bronze_path('sicar', 'sc'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_sc.parquet'), source_epsg=4674) }}