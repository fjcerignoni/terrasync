{{ config(
    materialized='external',
    location=export_path('scw', 'prodes_ce_opi')
) }}

select
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
    scene_id,
    publish_year,
    "source",
    satellite,
    sensor,
    {{ area_ha('geometry') }} as area_ha_calc,
    geometry
from {{ ref('slv_prodes') }}
where biome = 'cerrado'
  and image_date >= '2024-08-16'
