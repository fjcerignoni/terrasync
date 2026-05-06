{{ config(
    materialized='external',
    location='data/silver/stg_incra_assentamentos.parquet'
) }}

{{ clean_geometry('data/bronze/incra_assentamentos/*.parquet') }}
