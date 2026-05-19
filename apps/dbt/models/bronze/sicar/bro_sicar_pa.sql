{{ config(
    materialized='external',
    location=bronze_path('sicar', 'pa'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_pa.parquet'), source_epsg=4674) }}