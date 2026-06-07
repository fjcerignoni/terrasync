{{ config(
    materialized='external',
    location=silver_path('slv_inpe_bdqueimadas')
) }}

select * from {{ ref('bro_inpe_bdqueimadas') }}
