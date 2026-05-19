{{ config(
    materialized='external',
    location=staging_path('stg_deter_amazonia')
) }}

{{ clean_geometry(rawdata_path('deter', glob='deter_amazonia.parquet'), source_epsg=4674) }}
