{{ config(
    materialized='external',
    location='data/silver/stg_incra_snci_privado.parquet'
) }}

{{ clean_geometry('data/bronze/incra_snci_privado/*.parquet') }}
