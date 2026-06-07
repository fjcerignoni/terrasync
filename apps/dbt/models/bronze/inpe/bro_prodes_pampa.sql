{{ config(
    materialized='external',
    location=bronze_path('prodes', 'pampa'),
    tags=['bronze']
) }}

{% set source_rel %}
select
    * exclude (scene_id),
    'pampa' as biome,
    cast(scene_id as double) as scene_id
from read_parquet(
    '{{ rawdata_path("prodes", glob="prodes_pampa.parquet") }}'
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