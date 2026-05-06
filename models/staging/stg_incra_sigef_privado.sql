{{ config(
    materialized='external',
    location='data/silver/stg_incra_sigef_privado.parquet'
) }}

{{ clean_geometry('data/bronze/incra_sigef_privado/*.parquet') }}
