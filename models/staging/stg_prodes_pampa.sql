{{ config(
    materialized='external',
    location='data/silver/stg_prodes_pampa.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_pampa/*.parquet') }}
