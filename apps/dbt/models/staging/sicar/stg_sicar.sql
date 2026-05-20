{{ config(
    materialized='external',
    location=staging_path('stg_sicar')
) }}

-- Colunas abertas explicitamente: SICAR tem schema divergente entre UFs.
-- 12 UFs nao tem data_atualizacao: PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO.
-- union_by_name=true alinha os 27 parquets, coluna ausente vira NULL.

{% set sicar_source %}
SELECT
    cod_imovel,
    status_imovel,
    dat_criacao,
    data_atualizacao,
    area,
    condicao,
    uf,
    municipio,
    cod_municipio_ibge,
    m_fiscal,
    tipo_imovel,
    geometry
FROM {{ source('rawdata_sicar', 'sicar') }}
{% endset %}

{{ clean_geometry(relation=sicar_source, source_epsg=4674) }}
