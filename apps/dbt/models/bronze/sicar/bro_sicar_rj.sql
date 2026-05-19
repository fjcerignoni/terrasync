{{ config(
    materialized='external',
    location=bronze_path('sicar', 'rj'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_rj.parquet'), source_epsg=4674) }}