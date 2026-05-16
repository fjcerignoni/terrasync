"""DuckDB-backed queries used by the dashboard. Cached via Streamlit.

Each query opens a fresh in-memory DuckDB (with spatial loaded) to avoid
contention with the persistent `data/terrasync.duckdb` file used by `transform`.
"""

from __future__ import annotations

import duckdb
import streamlit as st


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except Exception:
        pass
    return con


@st.cache_data(ttl=60, show_spinner=False)
def actual_row_count(parquet_path: str, mtime: float) -> int:
    """Real row count via DuckDB. mtime invalidates cache when file is rewritten."""
    del mtime  # only used for cache key
    con = _connect()
    try:
        result = con.execute(
            "SELECT COUNT(*) FROM read_parquet(?)", [parquet_path]
        ).fetchone()
        return int(result[0]) if result else 0
    finally:
        con.close()
