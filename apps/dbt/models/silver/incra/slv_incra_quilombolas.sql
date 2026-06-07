{{ config(
    materialized='external',
    location=silver_path('slv_incra_quilombolas')
) }}

select * from {{ ref('bro_incra_quilombolas_lim_quilombolas_a') }}
