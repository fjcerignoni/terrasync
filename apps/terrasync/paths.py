"""Filesystem path constants resolved relative to the repository root."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """Walk up from this file to find pyproject.toml. Decouples from cwd."""
    p = Path(__file__).resolve()
    for parent in [p, *p.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("repo root (pyproject.toml) not found")


REPO_ROOT = repo_root()
DATA_DIR = REPO_ROOT / "data"
DBT_DIR = REPO_ROOT / "apps" / "dbt"
DBT_TARGET = DBT_DIR / "target"
