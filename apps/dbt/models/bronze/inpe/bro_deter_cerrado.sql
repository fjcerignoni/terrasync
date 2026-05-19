{{ config(
    materialized='external',
    location=bronze_path('deter', 'cerrado'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('deter', glob='deter_cerrado.parquet'), source_epsg=4674) }}