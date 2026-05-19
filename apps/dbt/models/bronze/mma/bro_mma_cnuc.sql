{{ config(
    materialized='external',
    location=bronze_path('mma', 'cnuc'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('mma', glob='mma_cnuc.parquet'), source_epsg=4674) }}