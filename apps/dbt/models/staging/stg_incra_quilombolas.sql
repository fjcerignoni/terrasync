{{ config(
    materialized='external',
    location='data/staging/stg_incra_quilombolas.parquet'
) }}

{{ clean_geometry('data/bronze/incra_quilombolas/*.parquet', source_epsg=4674) }}
