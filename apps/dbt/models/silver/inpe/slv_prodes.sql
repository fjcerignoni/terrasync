{{ config(
    materialized='external',
    location=silver_path('slv_prodes')
) }}

-- union_by_name alinha schemas entre biomas (cerrado usa uid->uuid;
-- pampa tem scene_id como DOUBLE — normalizado no bronze).
select * from {{ ref('bro_prodes_amazonia') }}
union all by name
select * from {{ ref('bro_prodes_caatinga') }}
union all by name
select * from {{ ref('bro_prodes_cerrado') }}
union all by name
select * from {{ ref('bro_prodes_mata_atlantica') }}
union all by name
select * from {{ ref('bro_prodes_pampa') }}
union all by name
select * from {{ ref('bro_prodes_pantanal') }}
