{{ config(
    materialized='external',
    location='data/silver/stg_incra_quilombolas.parquet'
) }}

{{ clean_geometry('data/bronze/incra_quilombolas/*.parquet') }}
