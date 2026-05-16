"""Acquisition manifest: per-layer JSONL run log + parquet footer metadata reader.

Two persistence surfaces for bronze provenance:
- Parquet footer key-value metadata (written by the downloader strategies).
- JSONL run log at ``data/manifests/runs.jsonl`` — one append per layer attempt.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq

from .config import MANIFESTS_DIR, DataSource

logger = logging.getLogger("terrasync.manifest")

_RUNS_FILE = MANIFESTS_DIR / "runs.jsonl"

Status = Literal["ok", "empty", "failed"]

_FOOTER_PREFIX = "terrasync."


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def footer_metadata(
    source: DataSource,
    layer_id: str,
    *,
    acquired_at: str,
    endpoint: str,
    n_features: int,
) -> dict[bytes, bytes]:
    """Bytes-keyed metadata dict for parquet footer key-value storage."""
    return {
        b"terrasync.acquired_at": acquired_at.encode(),
        b"terrasync.source": source.name.encode(),
        b"terrasync.layer_id": layer_id.encode(),
        b"terrasync.endpoint": endpoint.encode(),
        b"terrasync.source_epsg": str(source.epsg).encode(),
        b"terrasync.n_features": str(n_features).encode(),
    }


def build_entry(
    source: DataSource,
    layer_id: str,
    *,
    acquired_at: str,
    duration_s: float,
    status: Status,
    endpoint: str | None = None,
    n_features: int = 0,
    error: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "acquired_at": acquired_at,
        "source": source.name,
        "layer_id": layer_id,
        "endpoint": endpoint,
        "n_features": n_features,
        "duration_s": round(duration_s, 2),
        "source_epsg": source.epsg,
        "status": status,
    }
    if error is not None:
        entry["error"] = error
    return entry


def append_run(entry: dict[str, Any]) -> None:
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False)
    with _RUNS_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_parquet_metadata(path: Path | str) -> dict[str, str]:
    """Return only the ``terrasync.*`` footer entries, stripped of the prefix."""
    raw = pq.read_metadata(path).metadata or {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        key = k.decode("utf-8", errors="replace")
        if key.startswith(_FOOTER_PREFIX):
            out[key[len(_FOOTER_PREFIX):]] = v.decode("utf-8", errors="replace")
    return out
