{{ config(
    materialized='external',
    location=bronze_path('prodes', 'mata_atlantica'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('prodes', glob='prodes_mata_atlantica.parquet'), source_epsg=4674) }}