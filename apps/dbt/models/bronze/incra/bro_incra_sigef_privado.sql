{{ config(
    materialized='external',
    location=bronze_path('incra_sigef', 'privado'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('incra_sigef', glob='incra_sigef_privado.parquet'), source_epsg=4674) }}