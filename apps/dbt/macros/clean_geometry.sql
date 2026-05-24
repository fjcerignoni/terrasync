{% macro clean_geometry(parquet_path=none, source_epsg=4674, relation=none) %}
WITH raw AS (
    {% if relation is not none -%}
    {{ relation }}
    {%- else -%}
    SELECT * FROM read_parquet('{{ parquet_path }}')
    {%- endif %}
),
flattened AS (
    SELECT
        * EXCLUDE (geometry),
        ST_Force2D(geometry) AS geometry
    FROM raw
    WHERE geometry IS NOT NULL
),
validated AS (
    SELECT
        * EXCLUDE (geometry),
        CASE
            WHEN ST_IsValid(geometry) THEN ST_Multi(geometry)
            ELSE ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Buffer(geometry,0)), 3))
        END AS geometry_valid
    FROM flattened
),
reprojected AS (
    SELECT
        * EXCLUDE (geometry_valid),
        {% if source_epsg == 4326 %}
        geometry_valid AS geometry
        {% else %}
        ST_Transform(
            geometry_valid,
            'EPSG:{{ source_epsg }}',
            'EPSG:4326',
            always_xy := true
        ) AS geometry
        {% endif %}
    FROM validated
)
SELECT *
FROM reprojected
WHERE geometry IS NOT NULL
  AND NOT ST_IsEmpty(geometry)
  AND ST_XMin(geometry) >= -180
  AND ST_YMin(geometry) >= -90
  AND ST_XMax(geometry) <= 180
  AND ST_YMax(geometry) <= 90
{% endmacro %}
