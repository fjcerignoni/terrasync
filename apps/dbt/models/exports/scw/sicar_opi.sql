{{ config(
    materialized='external',
    location=export_path('scw', 'sicar_opi')
) }}

-- Export do cliente scw / projeto opi.
-- Recorte: 11 UFs do SICAR sobre o silver compartilhado slv_sicar (validado + EPSG:4326).
-- area_ha_calc: area equal-area computada (EPSG:5880) — distinta de `area`, que vem da fonte.
--
-- Dedup: SICAR tem cod_imovel duplicado em raros casos (verificado: 2 dups no recorte,
-- 20 no staging completo). Mantemos a linha mais recente por
-- COALESCE(data_atualizacao, dat_criacao) DESC: quando data_atualizacao eh NULL na
-- linha (3 das 11 UFs do recorte — RO, RR, TO — nao tem essa coluna no bronze; UFs
-- com a coluna tambem tem NULLs parciais), o ranking cai para dat_criacao daquela
-- linha. Datas sao ISO 8601 ("YYYY-MM-DDTHH:MM:SS.sssZ"), sort lexicografico = sort
-- cronologico. Empate final (raro): dat_criacao DESC.

with ranked as (
    select
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
        {{ area_ha('geometry') }} as area_ha_calc,
        geometry,
        row_number() over (
            partition by cod_imovel
            order by coalesce(data_atualizacao, dat_criacao) desc nulls last,
                     dat_criacao desc nulls last
        ) as _rn
    from {{ ref('slv_sicar') }}
    where uf in ('AC', 'AM', 'AP', 'DF', 'GO', 'MA', 'MT', 'PA', 'RO', 'RR', 'TO')
)

select
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
from ranked
where _rn = 1
