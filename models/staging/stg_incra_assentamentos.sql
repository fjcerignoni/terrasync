{{ config(
    materialized='external',
    location='data/staging/stg_incra_assentamentos.parquet'
) }}

{{ clean_geometry('data/bronze/incra_assentamentos/*.parquet', source_epsg=4674) }}
