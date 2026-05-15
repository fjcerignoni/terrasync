{{ config(
    materialized='external',
    location=staging_path('stg_sfb_concessoes')
) }}

{{ clean_geometry(bronze_path('sfb', 'sfb_concessoes.parquet'), source_epsg=4674) }}
