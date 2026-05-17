SELECT
    COUNT(*) FILTER (WHERE geometry IS NOT NULL) AS checked,
    COUNT(*) FILTER (WHERE geometry IS NOT NULL AND NOT ST_IsValid(geometry)) AS n_invalid
FROM read_parquet(?)
