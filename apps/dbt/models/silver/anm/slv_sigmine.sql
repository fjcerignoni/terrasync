{{ config(
    materialized='external',
    location=silver_path('slv_sigmine')
) }}

select * from {{ ref('bro_anm_sigmine') }}
