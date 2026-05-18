"""Read-only access to dbt artifacts (manifest.json + run_results.json).

Cached by file mtime so a `dbt build` rerun is picked up without restarting
Streamlit. Returns `None` when artifacts are missing; callers handle gracefully.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import streamlit as st

from ..paths import DBT_TARGET

_MANIFEST = DBT_TARGET / "manifest.json"
_RUN_RESULTS = DBT_TARGET / "run_results.json"
_MODEL_PREFIX = "model.terrasync."


@dataclass
class ModelInfo:
    name: str
    unique_id: str
    materialized: str
    depends_on: list[str] = field(default_factory=list)
    last_run_status: str | None = None
    last_run_duration_s: float | None = None
    last_run_message: str | None = None
    test_count: int = 0
    tests_passed: int = 0
    tests_failed: int = 0


def _mtime_or_none(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return None


def manifest_path() -> Path:
    return _MANIFEST


def run_results_path() -> Path:
    return _RUN_RESULTS


@st.cache_data(show_spinner=False)
def _read_json(path_str: str, mtime: float) -> dict:
    del mtime
    with open(path_str, encoding="utf-8") as f:
        return json.load(f)


def read_manifest() -> dict | None:
    mtime = _mtime_or_none(_MANIFEST)
    if mtime is None:
        return None
    return _read_json(str(_MANIFEST), mtime)


def read_run_results() -> dict | None:
    mtime = _mtime_or_none(_RUN_RESULTS)
    if mtime is None:
        return None
    return _read_json(str(_RUN_RESULTS), mtime)


def manifest_generated_at() -> str | None:
    m = read_manifest()
    if m is None:
        return None
    return m.get("metadata", {}).get("generated_at")


def run_results_generated_at() -> str | None:
    r = read_run_results()
    if r is None:
        return None
    return r.get("metadata", {}).get("generated_at")


def _strip_model_prefix(uid: str) -> str:
    if uid.startswith(_MODEL_PREFIX):
        return uid[len(_MODEL_PREFIX):]
    parts = uid.split(".")
    return parts[-1] if parts else uid


def model_summary() -> dict[str, ModelInfo]:
    """Map model name → ModelInfo combining manifest + run_results.

    Returns empty dict if manifest is absent. If only run_results is absent,
    models are returned with `last_run_*` fields unset.
    """
    manifest = read_manifest()
    if manifest is None:
        return {}
    nodes = manifest.get("nodes", {})

    models: dict[str, ModelInfo] = {}
    for uid, node in nodes.items():
        if node.get("resource_type") != "model":
            continue
        name = node.get("name", _strip_model_prefix(uid))
        materialized = node.get("config", {}).get("materialized", "view")
        depends_on = [
            _strip_model_prefix(u)
            for u in node.get("depends_on", {}).get("nodes", [])
        ]
        models[name] = ModelInfo(
            name=name,
            unique_id=uid,
            materialized=materialized,
            depends_on=depends_on,
        )

    # Index tests by the model they cover (depends_on.nodes[0]).
    tests_by_model: dict[str, list[str]] = {}
    for uid, node in nodes.items():
        if node.get("resource_type") != "test":
            continue
        deps = node.get("depends_on", {}).get("nodes", [])
        if not deps:
            continue
        target_model_name = _strip_model_prefix(deps[0])
        tests_by_model.setdefault(target_model_name, []).append(uid)

    for model_name, test_uids in tests_by_model.items():
        if model_name in models:
            models[model_name].test_count = len(test_uids)

    # Overlay last-run status/duration from run_results (model + tests).
    run_results = read_run_results()
    if run_results is not None:
        results_by_uid = {r["unique_id"]: r for r in run_results.get("results", [])}
        for name, info in models.items():
            r = results_by_uid.get(info.unique_id)
            if r is not None:
                info.last_run_status = r.get("status")
                info.last_run_duration_s = r.get("execution_time")
                info.last_run_message = r.get("message")
            # Count tests pass/fail.
            for test_uid in tests_by_model.get(name, []):
                rt = results_by_uid.get(test_uid)
                if rt is None:
                    continue
                if rt.get("status") == "pass":
                    info.tests_passed += 1
                elif rt.get("status") in ("fail", "error"):
                    info.tests_failed += 1

    return models
