{{ config(
    materialized='external',
    location=staging_path('stg_deter_cerrado')
) }}

{{ clean_geometry(rawdata_path('deter', glob='deter_cerrado.parquet'), source_epsg=4674) }}
