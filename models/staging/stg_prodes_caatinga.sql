{{ config(
    materialized='external',
    location='data/silver/stg_prodes_caatinga.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_caatinga/*.parquet') }}
