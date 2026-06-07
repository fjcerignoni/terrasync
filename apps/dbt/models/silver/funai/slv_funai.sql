{{ config(
    materialized='external',
    location=silver_path('slv_funai')
) }}

select * from {{ ref('bro_funai_tis_poligonais') }}
