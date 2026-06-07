{{ config(
    materialized='external',
    location=silver_path('slv_incra_snci')
) }}

select * from {{ ref('bro_incra_snci_privado') }}
union all by name
select * from {{ ref('bro_incra_snci_publico') }}
