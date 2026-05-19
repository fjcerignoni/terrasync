{{ config(
    materialized='external',
    location=staging_path('stg_sfb_cnfp')
) }}

{{ clean_geometry(rawdata_path('sfb', glob='sfb_cnfp.parquet'), source_epsg=4674) }}
