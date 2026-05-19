{{ config(
    materialized='external',
    location=bronze_path('incra_snci', 'publico'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('incra_snci', glob='incra_snci_publico.parquet'), source_epsg=4674) }}