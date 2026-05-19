{{ config(
    materialized='external',
    location=bronze_path('sicar', 'pr'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_pr.parquet'), source_epsg=4674) }}