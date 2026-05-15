{{ config(
    materialized='external',
    location='data/staging/stg_sicar.parquet'
) }}

-- Colunas abertas explicitamente: SICAR tem schema divergente entre UFs.
-- Divergencia (verificada): 12 UFs nao tem a coluna `data_atualizacao` —
-- PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO. Os outros 15 tem.
-- read_parquet(..., union_by_name=true) alinha os 27 parquets por nome: a coluna
-- ausente vira NULL nesses 12. Sem isso o glob estoura com "schema mismatch" no
-- primeiro arquivo divergente. Ajustes por estado (rename/cast/coalesce) entram aqui.

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
FROM read_parquet('data/bronze/sicar/*.parquet', union_by_name = true)
{% endset %}

{{ clean_geometry(relation=sicar_source, source_epsg=4674) }}
