{{ config(
    materialized='external',
    location=staging_path('stg_sigmine')
) }}

-- Colunas renomeadas para lowercase; case original do .dbf pode variar —
-- DuckDB resolve via case-insensitive matching no read_parquet.
{% set sigmine_source %}
SELECT
    PROCESSO     AS processo,
    ID           AS id,
    NUMERO       AS numero,
    ANO          AS ano,
    AREA_HA      AS area_ha,
    FASE         AS fase,
    ULT_EVENTO   AS ult_evento,
    NOME         AS nome,
    SUBS         AS subs,
    USO          AS uso,
    UF           AS uf,
    DSProcesso   AS ds_processo,
    geometry
FROM {{ source('rawdata_anm', 'sigmine') }}
{% endset %}

{{ clean_geometry(relation=sigmine_source, source_epsg=4674) }}
