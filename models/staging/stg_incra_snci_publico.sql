{{ config(
    materialized='external',
    location='data/staging/stg_incra_snci_publico.parquet'
) }}

{{ clean_geometry('data/bronze/incra_snci_publico/*.parquet', source_epsg=4674) }}
