{{ config(
    materialized='external',
    location='data/staging/stg_sfb_ifn_conglomerados.parquet'
) }}

{{ clean_geometry('data/bronze/sfb/ifn_conglomerados.parquet', source_epsg=4674) }}
