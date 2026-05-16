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


@st.cache_data(ttl=60, show_spinner=False)
def geom_health(parquet_path: str, mtime: float) -> dict[str, int]:
    """Cheap geometry quality scan: row count + null/empty geom counts.

    Returns zeros if the parquet has no `geom` column (e.g. attribute-only stg).
    """
    del mtime
    con = _connect()
    try:
        cols = con.execute(
            "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet(?))",
            [parquet_path],
        ).fetchall()
        has_geom = any(c[0] == "geom" for c in cols)
        if not has_geom:
            (total,) = con.execute(
                "SELECT COUNT(*) FROM read_parquet(?)", [parquet_path]
            ).fetchone()
            return {"rows": int(total), "n_null_geom": 0, "n_empty_geom": 0}
        row = con.execute(
            """
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE geom IS NULL),
                COUNT(*) FILTER (WHERE geom IS NOT NULL AND ST_IsEmpty(geom))
            FROM read_parquet(?)
            """,
            [parquet_path],
        ).fetchone()
        return {
            "rows": int(row[0]),
            "n_null_geom": int(row[1]),
            "n_empty_geom": int(row[2]),
        }
    finally:
        con.close()


@st.cache_data(ttl=3600, show_spinner="Validando geometrias…")
def validate_geometries(parquet_path: str, mtime: float) -> dict[str, int]:
    """Expensive `ST_IsValid` scan. Cached aggressively; invalidates on mtime."""
    del mtime
    con = _connect()
    try:
        cols = con.execute(
            "SELECT column_name FROM (DESCRIBE SELECT * FROM read_parquet(?))",
            [parquet_path],
        ).fetchall()
        has_geom = any(c[0] == "geom" for c in cols)
        if not has_geom:
            return {"n_invalid": 0, "checked": 0}
        row = con.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE geom IS NOT NULL),
                COUNT(*) FILTER (WHERE geom IS NOT NULL AND NOT ST_IsValid(geom))
            FROM read_parquet(?)
            """,
            [parquet_path],
        ).fetchone()
        return {"checked": int(row[0]), "n_invalid": int(row[1])}
    finally:
        con.close()
