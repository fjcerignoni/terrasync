{{ config(
    materialized='external',
    location=bronze_path('prodes', 'amazonia'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('prodes', glob='prodes_amazonia.parquet'), source_epsg=4674) }}