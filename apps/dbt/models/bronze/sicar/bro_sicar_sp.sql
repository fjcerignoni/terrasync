{{ config(
    materialized='external',
    location=bronze_path('sicar', 'sp'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_sp.parquet'), source_epsg=4674) }}