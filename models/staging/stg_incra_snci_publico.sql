{{ config(
    materialized='external',
    location='data/silver/stg_incra_snci_publico.parquet'
) }}

{{ clean_geometry('data/bronze/incra_snci_publico/*.parquet') }}
