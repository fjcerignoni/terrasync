{{ config(
    materialized='external',
    location='data/silver/stg_sfb_ifn_conglomerados.parquet'
) }}

{{ clean_geometry('data/bronze/sfb/ifn_conglomerados.parquet') }}
