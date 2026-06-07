{{ config(
    materialized='external',
    location=silver_path('slv_incra_assentamentos')
) }}

select * from {{ ref('bro_incra_assentamentos_brasil') }}
