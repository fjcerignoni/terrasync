{{ config(
    materialized='external',
    location=bronze_path('anm_sigmine', 'brasil'),
    tags=['bronze']
) }}

{% set source_rel %}
select
    PROCESSO     as processo,
    ID           as id,
    NUMERO       as numero,
    ANO          as ano,
    AREA_HA      as area_ha,
    FASE         as fase,
    ULT_EVENTO   as ult_evento,
    NOME         as nome,
    SUBS         as subs,
    USO          as uso,
    UF           as uf,
    DSProcesso   as ds_processo,
    geometry
from read_parquet(
    '{{ rawdata_path("sigmine", glob="sigmine_brasil.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674,
        id_columns=['processo', 'id'],
        dedup_id=['id'],
        dedup_date='ano'
    )
}}
