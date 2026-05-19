{{ config(
    materialized='external',
    location=bronze_path('sicar', 'rn'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_rn.parquet'), source_epsg=4674) }}