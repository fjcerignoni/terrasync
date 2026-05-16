CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_parquet;

CREATE SCHEMA IF NOT EXISTS silver;

DO $$
DECLARE
    full_version text;
BEGIN
    SELECT postgis_full_version() INTO full_version;
    RAISE NOTICE 'PostGIS: %', full_version;
END $$;
