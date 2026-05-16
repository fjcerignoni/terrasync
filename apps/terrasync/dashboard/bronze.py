"""Scan bronze layer parquets: footer metadata + file stats per (source, layer)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import SOURCES, DataSource
from ..manifest import read_parquet_metadata
from .cadence import age_status as _cadence_age_status


def _layer_id_from_path(source: DataSource, path: Path) -> str:
    """Reverse of source_parquet_path: <source>_<layer>.parquet or <name>.parquet."""
    stem = path.stem
    prefix = f"{source.name}_"
    if stem.startswith(prefix):
        return stem[len(prefix):]
    return stem


def _age_days(acquired_at: str | None) -> float | None:
    if not acquired_at:
        return None
    try:
        dt = datetime.fromisoformat(acquired_at)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return delta.total_seconds() / 86400.0


def scan_bronze() -> list[dict[str, Any]]:
    """One row per parquet found under data/bronze/<source>/."""
    rows: list[dict[str, Any]] = []
    for source in SOURCES.values():
        bronze_dir = source.bronze_dir
        if not bronze_dir.exists():
            continue
        for parquet in sorted(bronze_dir.glob("*.parquet")):
            try:
                meta = read_parquet_metadata(parquet)
            except Exception as e:
                meta = {"_error": str(e)}
            stat = parquet.stat()
            acquired_at = meta.get("acquired_at")
            age = _age_days(acquired_at)
            try:
                n_features = int(meta.get("n_features", 0))
            except ValueError:
                n_features = 0
            cadence = getattr(source, "cadence", "unknown")
            rows.append(
                {
                    "source": source.name,
                    "layer": _layer_id_from_path(source, parquet),
                    "category": source.category,
                    "group": source.group or source.name,
                    "cadence": cadence,
                    "acquired_at": acquired_at,
                    "age_days": age,
                    "age_status": _cadence_age_status(age, cadence),
                    "n_features": n_features,
                    "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "endpoint": meta.get("endpoint", ""),
                    "source_epsg": meta.get("source_epsg", ""),
                    "path": str(parquet),
                    "mtime": stat.st_mtime,
                }
            )
    return rows
