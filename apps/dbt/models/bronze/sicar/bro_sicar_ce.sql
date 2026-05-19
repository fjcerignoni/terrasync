{{ config(
    materialized='external',
    location=bronze_path('sicar', 'ce'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_ce.parquet'), source_epsg=4674) }}