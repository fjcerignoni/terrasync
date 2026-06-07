{{ config(
    materialized='external',
    location=bronze_path('prodes', 'amazonia'),
    tags=['bronze']
) }}

{% set source_rel %}
select *, 'amazonia' as biome
from read_parquet(
    '{{ rawdata_path("prodes", glob="prodes_amazonia.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674,
        id_columns=['uuid'],
        dedup_id=['uuid'],
        dedup_date='image_date'
    )
}}