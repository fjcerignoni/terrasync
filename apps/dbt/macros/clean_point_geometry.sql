{% macro clean_point_geometry(parquet_path=none, source_epsg=4326, relation=none) %}
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
    WHERE geometry IS NOT NULL AND NOT ST_IsEmpty(geometry)
),
reprojected AS (
    SELECT
        * EXCLUDE (geometry),
        {% if source_epsg == 4326 %}
        geometry
        {% else %}
        ST_Transform(
            geometry,
            'EPSG:{{ source_epsg }}',
            'EPSG:4326',
            always_xy := true
        ) AS geometry
        {% endif %}
    FROM flattened
)
SELECT *
FROM reprojected
WHERE geometry IS NOT NULL
  AND NOT ST_IsEmpty(geometry)
  AND ST_X(geometry) >= -180 AND ST_Y(geometry) >= -90
  AND ST_X(geometry) <= 180  AND ST_Y(geometry) <= 90
{% endmacro %}
