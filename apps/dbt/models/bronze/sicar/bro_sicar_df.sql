{{ config(
    materialized='external',
    location=bronze_path('sicar', 'df'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_df.parquet'), source_epsg=4674) }}