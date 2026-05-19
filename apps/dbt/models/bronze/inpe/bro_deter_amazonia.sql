{{ config(
    materialized='external',
    location=bronze_path('deter', 'amazonia'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('deter', glob='deter_amazonia.parquet'), source_epsg=4674) }}