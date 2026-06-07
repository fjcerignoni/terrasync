{{ config(
    materialized='external',
    location=bronze_path('deter', 'cerrado'),
    tags=['bronze']
) }}

{% set source_rel %}
select *, 'cerrado' as biome
from read_parquet(
    '{{ rawdata_path("deter", glob="deter_cerrado.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674
    )
}}