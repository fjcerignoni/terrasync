"""Scan bronze layer parquets (dbt bro_* output): geometry quality metrics per (source, layer).

pct_drop = percentage of rawdata features lost after clean_geometry. A non-zero
value indicates geometries that were invalid and could not be repaired.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from ..config import BRONZE_DIR, SOURCES, DataSource


def _layer_id_from_path(source: DataSource, path: Path) -> str:
    """Reverse of source_parquet_path: <source>_<layer>.parquet → <layer>."""
    stem = path.stem
    prefix = f"{source.name}_"
    if stem.startswith(prefix):
        return stem[len(prefix):]
    return stem


def scan_bronze(rawdata_rows: list[dict] | None = None) -> list[dict[str, Any]]:
    """One row per parquet found under data/bronze/<source>/ (dbt bro_* output).

    Returns an empty list before any dbt bro_* model has been materialized.
    When rawdata_rows are provided, pct_drop is computed as the percentage of
    rawdata features that were removed by clean_geometry.
    """
    rawdata_counts: dict[tuple[str, str], int] = {}
    if rawdata_rows:
        for r in rawdata_rows:
            rawdata_counts[(r["source"], r["layer"])] = r["n_features"]

    rows: list[dict[str, Any]] = []
    for source in SOURCES.values():
        bronze_dir = BRONZE_DIR / source.name
        if not bronze_dir.exists():
            continue
        for parquet in sorted(bronze_dir.glob("*.parquet")):
            stat = parquet.stat()
            try:
                n_features = pq.read_metadata(parquet).num_rows
            except Exception:
                n_features = 0
            layer_id = _layer_id_from_path(source, parquet)
            rawdata_n = rawdata_counts.get((source.name, layer_id), 0)
            pct_drop = (
                round(100.0 * (rawdata_n - n_features) / rawdata_n, 2)
                if rawdata_n > 0
                else None
            )
            rows.append(
                {
                    "source": source.name,
                    "layer": layer_id,
                    "provider": getattr(source, "provider", None) or source.name,
                    "n_features": n_features,
                    "rawdata_features": rawdata_n or None,
                    "pct_drop": pct_drop,
                    "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "path": str(parquet),
                    "mtime": stat.st_mtime,
                }
            )
    return rows
