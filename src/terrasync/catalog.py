import logging
from pathlib import Path

import duckdb

from .config import DUCKDB_PATH, SOURCES, DATA_DIR

logger = logging.getLogger("terrasync.catalog")


def refresh_catalog() -> None:
    """Create/update DuckDB catalog with views pointing to bronze parquet files."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH))
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except duckdb.IOException:
        con.execute("LOAD spatial;")

    for key, source in SOURCES.items():
        bronze_dir = source.bronze_dir
        if not bronze_dir.exists():
            continue

        for parquet_file in sorted(bronze_dir.glob("*.parquet")):
            layer_id = parquet_file.stem
            view_name = f"bronze_{key}_{layer_id}"
            abs_path = parquet_file.resolve()
            con.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS "
                f"SELECT * FROM read_parquet('{abs_path}')"
            )
            logger.debug("Registered view: %s -> %s", view_name, abs_path)

    logger.info("Catalog refreshed: %s", DUCKDB_PATH)
    con.close()
