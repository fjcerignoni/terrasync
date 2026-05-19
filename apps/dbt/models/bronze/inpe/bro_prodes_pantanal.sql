{{ config(
    materialized='external',
    location=bronze_path('prodes', 'pantanal'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('prodes', glob='prodes_pantanal.parquet'), source_epsg=4674) }}