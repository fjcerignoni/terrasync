{{ config(
    materialized='external',
    location=bronze_path('sicar', 'pi'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_pi.parquet'), source_epsg=4674) }}