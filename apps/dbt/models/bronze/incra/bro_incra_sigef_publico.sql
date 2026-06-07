{{ config(
    materialized='external',
    location=bronze_path('incra_sigef', 'publico'),
    tags=['bronze']
) }}

{% set source_rel %}
select *, 'publico' as tipo
from read_parquet(
    '{{ rawdata_path("incra_sigef", glob="incra_sigef_publico.parquet") }}'
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