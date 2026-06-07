{{ config(
    materialized='external',
    location=export_path('scw', 'sigmine_opi')
) }}

select
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
    {{ area_ha('geometry') }} as area_ha_calc,
    geometry
from {{ ref('slv_sigmine') }}
where fase is not null
