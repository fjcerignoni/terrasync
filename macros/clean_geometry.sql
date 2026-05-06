{% macro clean_geometry(parquet_path) %}
WITH raw AS (
    SELECT * FROM read_parquet('{{ parquet_path }}')
),
validated AS (
    SELECT
        * EXCLUDE (geometry),
        CASE
            WHEN ST_IsValid(geometry) THEN geometry
            ELSE ST_CollectionExtract(ST_MakeValid(geometry), 3)
        END AS geometry
    FROM raw
    WHERE geometry IS NOT NULL
)
SELECT *
FROM validated
WHERE geometry IS NOT NULL
  AND NOT ST_IsEmpty(geometry)
  AND ST_XMin(geometry) >= -180
  AND ST_YMin(geometry) >= -90
  AND ST_XMax(geometry) <= 180
  AND ST_YMax(geometry) <= 90
{% endmacro %}
