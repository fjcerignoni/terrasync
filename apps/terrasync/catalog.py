"""DuckDB catalog management for terrasync bronze parquet views."""

import logging

import duckdb

from .config import DATA_DIR, DUCKDB_PATH, SOURCES, source_parquet_path

logger = logging.getLogger("terrasync.catalog")


def refresh_catalog() -> None:
    """Create/update DuckDB catalog with views pointing to bronze parquet files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except duckdb.IOException:
        con.execute("LOAD spatial;")

    stale = con.execute(
        "SELECT table_name FROM information_schema.views "
        "WHERE table_schema = current_schema() "
        "AND (table_name LIKE 'rawdata_%' OR table_name LIKE 'bronze_%')"
    ).fetchall()
    for (view_name,) in stale:
        con.execute(f'DROP VIEW IF EXISTS "{view_name}"')
    if stale:
        logger.info("Dropped %d existing rawdata_*/bronze_* view(s).", len(stale))

    registered = 0
    for key, source in SOURCES.items():
        for layer_id in source.layer_ids:
            parquet_file = source_parquet_path(source, layer_id)
            if not parquet_file.exists():
                continue
            view_name = f"rawdata_{key}_{layer_id}"
            abs_path = parquet_file.resolve().as_posix()
            con.execute(
                f'CREATE OR REPLACE VIEW "{view_name}" AS '
                f"SELECT * FROM read_parquet('{abs_path}')"
            )
            logger.debug("Registered view: %s -> %s", view_name, abs_path)
            registered += 1

    logger.info("Catalog refreshed: %d view(s) in %s", registered, DUCKDB_PATH)
    con.close()
