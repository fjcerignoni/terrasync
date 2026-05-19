"""Scan staging layer parquets and cross-reference with dbt staging models.

Mapping bronze ↔ staging is by textual convention: `stg_<source>[_<layer>].parquet`
corresponds to one source under `data/bronze/<source>/`. Longest source-name
prefix wins (so `stg_incra_sigef_privado` resolves to source `incra_sigef_privado`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import SOURCES, STAGING_DIR
from ..paths import DBT_DIR

_STG_MODELS_DIR = DBT_DIR / "models" / "staging"


def _list_dbt_staging_models() -> list[str]:
    if not _STG_MODELS_DIR.exists():
        return []
    return sorted(p.stem for p in _STG_MODELS_DIR.rglob("stg_*.sql"))


def _resolve_source_for_model(model: str) -> str | None:
    """`stg_incra_sigef_privado` → `incra_sigef_privado`; `stg_sicar` → `sicar`.

    Longest-prefix match against known source names. Returns None if no source
    name is a prefix of the model basename after stripping `stg_`.
    """
    if not model.startswith("stg_"):
        return None
    basename = model[len("stg_"):]
    candidates = [
        name for name in SOURCES.keys()
        if basename == name or basename.startswith(f"{name}_")
    ]
    if not candidates:
        return None
    return max(candidates, key=len)


def scan_staging() -> list[dict[str, Any]]:
    """One row per staging model. Built models carry parquet stats; missing
    models appear with `built=False` and empty stats."""
    rows: list[dict[str, Any]] = []
    models = _list_dbt_staging_models()
    # Include any parquet that exists without a dbt model (defensive).
    parquet_only = sorted(
        p.stem for p in STAGING_DIR.glob("stg_*.parquet")
        if p.stem not in models
    )

    for model in [*models, *parquet_only]:
        parquet = STAGING_DIR / f"{model}.parquet"
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
