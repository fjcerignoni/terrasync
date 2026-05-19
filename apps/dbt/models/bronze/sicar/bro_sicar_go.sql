{{ config(
    materialized='external',
    location=bronze_path('sicar', 'go'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_go.parquet'), source_epsg=4674) }}