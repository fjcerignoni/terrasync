{{ config(
    materialized='external',
    location=bronze_path('nasa_firms', 'viirs_noaa20'),
    tags=['bronze']
) }}

{{ clean_point_geometry(rawdata_path('nasa_firms', glob='nasa_firms_viirs_noaa20_*.parquet'), source_epsg=4326) }}
