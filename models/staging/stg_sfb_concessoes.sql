{{ config(
    materialized='external',
    location='data/silver/stg_sfb_concessoes.parquet'
) }}

{{ clean_geometry('data/bronze/sfb/concessoes.parquet') }}
