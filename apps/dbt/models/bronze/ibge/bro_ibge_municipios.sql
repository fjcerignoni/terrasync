{{ config(
    materialized='external',
    location=bronze_path('ibge', 'municipios'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('ibge', glob='ibge_municipios.parquet'), source_epsg=4674) }}