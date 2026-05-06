{{ config(
    materialized='external',
    location='data/silver/stg_prodes_amazonia.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_amazonia/*.parquet') }}
