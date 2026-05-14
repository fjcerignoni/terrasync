{{ config(
    materialized='external',
    location='data/staging/stg_prodes_pantanal.parquet'
) }}

{{ clean_geometry('data/bronze/prodes_pantanal/*.parquet', source_epsg=4674) }}
