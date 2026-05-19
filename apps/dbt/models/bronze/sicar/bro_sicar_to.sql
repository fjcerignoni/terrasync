{{ config(
    materialized='external',
    location=bronze_path('sicar', 'to'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_to.parquet'), source_epsg=4674) }}