{{ config(
    materialized='external',
    location=bronze_path('sicar', 'mg'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_mg.parquet'), source_epsg=4674) }}