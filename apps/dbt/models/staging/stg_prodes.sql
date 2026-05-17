{{ config(
    materialized='external',
    location=staging_path('stg_prodes')
) }}

-- Une os 6 parquets PRODES (1 por bioma) em data/bronze/prodes/*.parquet.
-- union_by_name=true alinha as colunas (ordem varia entre biomas).
-- CAST scene_id::DOUBLE porque pampa veio BIGINT e os outros DOUBLE — sem isso
-- o read_parquet estoura com "type mismatch" no primeiro arquivo divergente.
-- biome é derivado do filename (não existe nas colunas da fonte).

{% set prodes_source %}
SELECT
    regexp_extract(filename, 'prodes_([a-z_]+?)_yearly_deforestation', 1) AS biome,
    uuid,
    uid,
    state,
    path_row,
    main_class,
    class_name,
    def_cloud,
    julian_day,
    image_date,
    "year",
    area_km,
    CAST(scene_id AS DOUBLE) AS scene_id,
    publish_year,
    "source",
    satellite,
    sensor,
    ST_Force2D(geometry) AS geometry
FROM read_parquet('{{ bronze_path("prodes") }}', union_by_name = true, filename = true)
{% endset %}

{{ clean_geometry(relation=prodes_source, source_epsg=4674) }}
