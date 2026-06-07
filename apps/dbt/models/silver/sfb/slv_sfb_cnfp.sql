{{ config(
    materialized='external',
    location=silver_path('slv_sfb_cnfp')
) }}

select * from {{ ref('bro_sfb_cnfp') }}
