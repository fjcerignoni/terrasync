{{ config(
    materialized='external',
    location=bronze_path('incra_assentamentos', 'brasil'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('incra_assentamentos', glob='incra_assentamentos_brasil.parquet'), source_epsg=4674) }}