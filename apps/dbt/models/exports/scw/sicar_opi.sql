{{ config(
    materialized='external',
    location='data/exports/scw/sicar_opi/v=' ~ var('scw_data_version', run_started_at.strftime('%Y-%m-%d')) ~ '/sicar_opi.parquet'
) }}

-- Export do cliente scw / projeto opi.
-- Recorte: 11 UFs do SICAR sobre o staging compartilhado stg_sicar (validado + EPSG:4326).
-- area_ha_calc: area equal-area computada (EPSG:5880) — distinta de `area`, que vem da fonte.
--
-- Dedup: SICAR tem cod_imovel duplicado em raros casos (verificado: 2 dups no recorte,
-- 20 no staging completo). Mantemos a linha mais recente por
-- COALESCE(data_atualizacao, dat_criacao) DESC: quando data_atualizacao eh NULL na
-- linha (3 das 11 UFs do recorte — RO, RR, TO — nao tem essa coluna no bronze; UFs
-- com a coluna tambem tem NULLs parciais), o ranking cai para dat_criacao daquela
-- linha. Datas sao ISO 8601 ("YYYY-MM-DDTHH:MM:SS.sssZ"), sort lexicografico = sort
-- cronologico. Empate final (raro): dat_criacao DESC.

WITH ranked AS (
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
        {{ area_ha('geometry') }} AS area_ha_calc,
        geometry,
        row_number() OVER (
            PARTITION BY cod_imovel
            ORDER BY COALESCE(data_atualizacao, dat_criacao) DESC NULLS LAST,
                     dat_criacao DESC NULLS LAST
        ) AS _rn
    FROM {{ ref('stg_sicar') }}
    WHERE uf IN ('AC', 'AM', 'AP', 'DF', 'GO', 'MA', 'MT', 'PA', 'RO', 'RR', 'TO')
)

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
    area_ha_calc,
    geometry
FROM ranked
WHERE _rn = 1
