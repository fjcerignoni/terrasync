{{ config(
    materialized='external',
    location=silver_path('slv_sicar')
) }}

-- union_by_name alinha schemas entre UFs: 12 estados nao têm
-- data_atualizacao (PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO).
select * from {{ ref('bro_sicar_ac') }}
union all by name
select * from {{ ref('bro_sicar_al') }}
union all by name
select * from {{ ref('bro_sicar_am') }}
union all by name
select * from {{ ref('bro_sicar_ap') }}
union all by name
select * from {{ ref('bro_sicar_ba') }}
union all by name
select * from {{ ref('bro_sicar_ce') }}
union all by name
select * from {{ ref('bro_sicar_df') }}
union all by name
select * from {{ ref('bro_sicar_es') }}
union all by name
select * from {{ ref('bro_sicar_go') }}
union all by name
select * from {{ ref('bro_sicar_ma') }}
union all by name
select * from {{ ref('bro_sicar_mg') }}
union all by name
select * from {{ ref('bro_sicar_ms') }}
union all by name
select * from {{ ref('bro_sicar_mt') }}
union all by name
select * from {{ ref('bro_sicar_pa') }}
union all by name
select * from {{ ref('bro_sicar_pb') }}
union all by name
select * from {{ ref('bro_sicar_pe') }}
union all by name
select * from {{ ref('bro_sicar_pi') }}
union all by name
select * from {{ ref('bro_sicar_pr') }}
union all by name
select * from {{ ref('bro_sicar_rj') }}
union all by name
select * from {{ ref('bro_sicar_rn') }}
union all by name
select * from {{ ref('bro_sicar_ro') }}
union all by name
select * from {{ ref('bro_sicar_rr') }}
union all by name
select * from {{ ref('bro_sicar_rs') }}
union all by name
select * from {{ ref('bro_sicar_sc') }}
union all by name
select * from {{ ref('bro_sicar_se') }}
union all by name
select * from {{ ref('bro_sicar_sp') }}
union all by name
select * from {{ ref('bro_sicar_to') }}
