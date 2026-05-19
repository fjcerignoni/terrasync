{{ config(
    materialized='external',
    location=bronze_path('funai', 'tis_poligonais'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('funai', glob='funai_tis_poligonais.parquet'), source_epsg=4674) }}