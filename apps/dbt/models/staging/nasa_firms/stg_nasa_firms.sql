{{ config(
    materialized='external',
    location=staging_path('stg_nasa_firms')
) }}

{% set firms_source %}
SELECT
    latitude,
    longitude,
    CAST(acq_date AS DATE) AS acq_date,
    CAST(acq_time AS VARCHAR) AS acq_time,
    satellite,
    instrument,
    confidence,
    frp,
    bright_ti4,
    daynight,
    geometry
FROM read_parquet('{{ rawdata_path("nasa_firms", glob="nasa_firms_viirs_noaa20_*.parquet") }}', union_by_name := true)
{% endset %}

{{ clean_point_geometry(relation=firms_source, source_epsg=4326) }}
