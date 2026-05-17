SELECT
    COUNT(*) AS rows,
    (SELECT ST_AsText(geometry) FROM read_parquet(?) LIMIT 1) AS sample_geom,
    COUNT(*) FILTER (WHERE geometry IS NULL) AS n_null_geom,
    COUNT(*) FILTER (WHERE geometry IS NOT NULL AND ST_IsEmpty(geometry)) AS n_empty_geom
FROM read_parquet(?)
