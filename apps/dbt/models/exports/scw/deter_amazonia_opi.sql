{{ config(
    materialized='external',
    location=export_path('scw', 'deter_amazonia_opi')
) }}

-- Export do cliente scw / projeto opi.
-- DETER Amazônia sem tratamento temático além do staging (geometria validada, EPSG:4326).
-- area_ha_calc: área equal-area computada (EPSG:5880) via macro area_ha.

SELECT
    gid,
    classname,
    quadrant,
    path_row,
    view_date,
    sensor,
    satellite,
    areauckm,
    uc,
    areamunkm,
    municipality,
    mun_geocod,
    uf,
    publish_month,
    {{ area_ha('geometry') }} AS area_ha_calc,
    geometry
FROM {{ ref('stg_deter') }}
WHERE biome = 'amazonia'
