{{ config(
    materialized='external',
    location=bronze_path('sicar', 'es'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_es.parquet'), source_epsg=4674) }}