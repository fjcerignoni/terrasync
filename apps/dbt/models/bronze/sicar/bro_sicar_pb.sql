{{ config(
    materialized='external',
    location=bronze_path('sicar', 'pb'),
    tags=['bronze']
) }}

{{ clean_geometry(rawdata_path('sicar', glob='sicar_pb.parquet'), source_epsg=4674) }}