{{ config(
    materialized='external',
    location='data/staging/stg_incra_sigef_privado.parquet'
) }}

{{ clean_geometry('data/bronze/incra_sigef_privado/*.parquet', source_epsg=4674) }}
