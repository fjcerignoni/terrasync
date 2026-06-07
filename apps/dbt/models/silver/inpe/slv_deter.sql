{{ config(
    materialized='external',
    location=silver_path('slv_deter')
) }}

select * from {{ ref('bro_deter_amazonia') }}
union all by name
select * from {{ ref('bro_deter_cerrado') }}
