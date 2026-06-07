{{ config(
    materialized='external',
    location=silver_path('slv_incra_sigef')
) }}

select * from {{ ref('bro_incra_sigef_privado') }}
union all by name
select * from {{ ref('bro_incra_sigef_publico') }}
