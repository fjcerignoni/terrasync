{{ config(
    materialized='external',
    location=bronze_path('sicar', 'rs'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_rs.parquet'), source_epsg=4674) }}