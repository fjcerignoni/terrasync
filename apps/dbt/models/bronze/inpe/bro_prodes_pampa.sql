{{ config(
    materialized='external',
    location=bronze_path('prodes', 'pampa'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('prodes', glob='prodes_pampa.parquet'), source_epsg=4674) }}