{{ config(
    materialized='external',
    location='data/staging/stg_icmbio.parquet'
) }}

{{ clean_geometry('data/bronze/icmbio/*.parquet', source_epsg=4674) }}
