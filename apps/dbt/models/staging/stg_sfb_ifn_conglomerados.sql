{{ config(
    materialized='external',
    location=staging_path('stg_sfb_ifn_conglomerados')
) }}

{{ clean_geometry(bronze_path('sfb', 'sfb_ifn_conglomerados.parquet'), source_epsg=4674) }}
