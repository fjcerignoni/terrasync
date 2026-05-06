{{ config(
    materialized='external',
    location='data/silver/stg_sfb_cnfp.parquet'
) }}

{{ clean_geometry('data/bronze/sfb/cnfp.parquet') }}
