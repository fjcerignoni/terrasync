{{ config(
    materialized='external',
    location=export_path('scw', 'sigmine_opi')
) }}

SELECT
    processo,
    id,
    numero,
    ano,
    area_ha,
    fase,
    ult_evento,
    nome,
    subs,
    uso,
    uf,
    ds_processo,
    {{ area_ha('geometry') }} AS area_ha_calc,
    geometry
FROM {{ ref('stg_sigmine') }}
