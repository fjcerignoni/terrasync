{{ config(
    materialized='external',
    location=bronze_path('incra_quilombolas', 'lim_quilombolas_a'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('incra_quilombolas', glob='incra_quilombolas_lim_quilombolas_a.parquet'), source_epsg=4674) }}