{{ config(
    materialized='external',
    location='data/silver/stg_prodes_pantanal.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_pantanal/*.parquet') }}
