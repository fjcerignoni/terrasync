{{ config(
    materialized='external',
    location=bronze_path('incra_sigef', 'privado'),
    tags=['bronze']
) }}

{% set source_rel %}
select *, 'privado' as tipo
from read_parquet(
    '{{ rawdata_path("incra_sigef", glob="incra_sigef_privado.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674,
        id_columns=['parcela_co'],
        dedup_id=['parcela_co'],
        dedup_date='data_aprov'
    )
}}