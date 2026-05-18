"""Reader for data/manifests/runs.jsonl — one row per layer ingest attempt.

Schema (from terrasync.manifest.build_entry):
    acquired_at, source, layer_id, endpoint, n_features, duration_s,
    source_epsg, status, [error]
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..config import MANIFESTS_DIR

_RUNS_FILE = MANIFESTS_DIR / "runs.jsonl"


@st.cache_data(ttl=30, show_spinner=False)
def read_runs(mtime: float, limit: int = 500) -> pd.DataFrame:
    """Read last `limit` entries from runs.jsonl. Empty DataFrame if missing."""
    del mtime  # cache key only
    if not _RUNS_FILE.exists():
        return pd.DataFrame(
            columns=[
                "acquired_at",
                "source",
                "layer_id",
                "endpoint",
                "n_features",
                "duration_s",
                "source_epsg",
                "status",
                "error",
            ]
        )
    df = pd.read_json(_RUNS_FILE, lines=True)
    if df.empty:
        return df
    df["acquired_at"] = pd.to_datetime(df["acquired_at"], errors="coerce", utc=True)
    df = df.sort_values("acquired_at", ascending=False).head(limit).reset_index(drop=True)
    if "error" not in df.columns:
        df["error"] = None
    return df


def runs_mtime() -> float:
    """Used as cache key so the dataframe refreshes after a new ingest."""
    return _RUNS_FILE.stat().st_mtime if _RUNS_FILE.exists() else 0.0
