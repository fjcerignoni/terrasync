"""Scan silver layer parquets and cross-reference with dbt silver models.

Mapping bronze ↔ silver is by textual convention: `slv_<source>[_<layer>].parquet`
corresponds to one source under `data/bronze/<source>/`. Longest source-name
prefix wins (so `slv_incra_sigef_privado` resolves to source `incra_sigef_privado`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import SOURCES, SILVER_DIR
from ..paths import DBT_DIR

_SLV_MODELS_DIR = DBT_DIR / "models" / "silver"


def _list_dbt_silver_models() -> list[str]:
    if not _SLV_MODELS_DIR.exists():
        return []
    return sorted(p.stem for p in _SLV_MODELS_DIR.rglob("slv_*.sql"))


def _resolve_source_for_model(model: str) -> str | None:
    """`slv_incra_sigef_privado` → `incra_sigef_privado`; `slv_sicar` → `sicar`.

    Longest-prefix match against known source names. Returns None if no source
    name is a prefix of the model basename after stripping `slv_`.
    """
    if not model.startswith("slv_"):
        return None
    basename = model[len("slv_"):]
    candidates = [
        name for name in SOURCES.keys()
        if basename == name or basename.startswith(f"{name}_")
    ]
    if not candidates:
        return None
    return max(candidates, key=len)


def scan_silver() -> list[dict[str, Any]]:
    """One row per silver model. Built models carry parquet stats; missing
    models appear with `built=False` and empty stats."""
    rows: list[dict[str, Any]] = []
    models = _list_dbt_silver_models()
    # Include any parquet that exists without a dbt model (defensive).
    parquet_only = sorted(
        p.stem for p in SILVER_DIR.glob("slv_*.parquet")
        if p.stem not in models
    )

    for model in [*models, *parquet_only]:
        parquet = SILVER_DIR / f"{model}.parquet"
        source = _resolve_source_for_model(model)
        if parquet.exists():
            stat = parquet.stat()
            rows.append(
                {
                    "model": model,
                    "built": True,
                    "source": source or "",
                    "path": str(parquet),
                    "mtime": stat.st_mtime,
                    "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
                }
            )
        else:
            rows.append(
                {
                    "model": model,
                    "built": False,
                    "source": source or "",
                    "path": None,
                    "mtime": None,
                    "file_size_mb": None,
                }
            )
    return rows
