{{ config(
    materialized='external',
    location='data/staging/stg_sfb_cnfp.parquet'
) }}

{{ clean_geometry('data/bronze/sfb/cnfp.parquet', source_epsg=4674) }}
