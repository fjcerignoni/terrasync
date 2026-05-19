{{ config(
    materialized='external',
    location=bronze_path('incra_sigef', 'publico'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('incra_sigef', glob='incra_sigef_publico.parquet'), source_epsg=4674) }}