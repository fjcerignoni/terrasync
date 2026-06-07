{{ config(
    materialized='external',
    location=bronze_path('prodes', 'pantanal'),
    tags=['bronze']
) }}

{% set source_rel %}
select *, 'pantanal' as biome
from read_parquet(
    '{{ rawdata_path("prodes", glob="prodes_pantanal.parquet") }}'
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