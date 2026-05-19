{{ config(
    materialized='external',
    location=bronze_path('prodes', 'cerrado'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('prodes', glob='prodes_cerrado.parquet'), source_epsg=4674) }}