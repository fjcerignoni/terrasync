{{ config(
    materialized='external',
    location=staging_path('stg_prodes')
) }}

-- Une os 6 parquets PRODES (1 por bioma) em data/rawdata/prodes/*.parquet.
-- union_by_name=true alinha as colunas (ordem varia entre biomas).
-- CAST scene_id::DOUBLE porque pampa veio BIGINT e os outros DOUBLE.
-- biome derivado do filename (prodes_{biome}.parquet).

{% set prodes_source %}
SELECT
    regexp_extract(filename, 'prodes_([a-z_]+?)\.parquet', 1) AS biome,
    uuid,
    uid,
    state,
    path_row,
    main_class,
    class_name,
    def_cloud,
    julian_day,
    image_date,
    "year",
    area_km,
    CAST(scene_id AS DOUBLE) AS scene_id,
    publish_year,
    "source",
    satellite,
    sensor,
    ST_Force2D(geometry) AS geometry
FROM {{ source('rawdata_inpe', 'prodes') }}
{% endset %}

{{ clean_geometry(relation=prodes_source, source_epsg=4674) }}
