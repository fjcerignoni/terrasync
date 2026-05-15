{{ config(
    materialized='external',
    location=staging_path('stg_sfb_cnfp')
) }}

{{ clean_geometry(bronze_path('sfb', 'cnfp.parquet'), source_epsg=4674) }}
