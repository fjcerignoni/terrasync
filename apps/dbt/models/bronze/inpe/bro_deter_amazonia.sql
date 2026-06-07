{{ config(
    materialized='external',
    location=bronze_path('deter', 'amazonia'),
    tags=['bronze']
) }}

{% set source_rel %}
select *, 'amazonia' as biome
from read_parquet(
    '{{ rawdata_path("deter", glob="deter_amazonia.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674,
        id_columns=['gid','path_row'],
        dedup_id=['gid', 'path_row'],
        dedup_date='view_date'
    )
}}