{{ config(
    materialized='external',
    location=bronze_path('incra_snci', 'privado'),
    tags=['bronze']
) }}

{% set source_rel %}
select *, 'privado' as tipo
from read_parquet(
    '{{ rawdata_path("incra_snci", glob="incra_snci_privado.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674,
        id_columns=['num_certif'],
        dedup_id=['num_certif'],
        dedup_date='data_certi'
    )
}}