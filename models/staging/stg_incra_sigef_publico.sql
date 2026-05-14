{{ config(
    materialized='external',
    location='data/staging/stg_incra_sigef_publico.parquet'
) }}

{{ clean_geometry('data/bronze/incra_sigef_publico/*.parquet', source_epsg=4674) }}
