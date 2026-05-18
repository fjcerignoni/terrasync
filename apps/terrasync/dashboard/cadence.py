"""Cadence-aware age semaphore.

Pure functions; no streamlit/duckdb deps so this is trivially unit-testable.
Thresholds calibrated against the catalogue's update rhythms:
DETER (~daily), monthly drops, quarterly publications, yearly snapshots
(PRODES, SICAR, INCRA, IBGE).
"""

from __future__ import annotations

from typing import Literal

Cadence = Literal["daily", "weekly", "monthly", "quarterly", "yearly", "unknown"]
AgeStatus = Literal["green", "yellow", "red", "gray"]


_THRESHOLDS: dict[str, tuple[float, float]] = {
    "daily":     (2, 7),
    "weekly":    (10, 30),
    "monthly":   (40, 90),
    "quarterly": (120, 270),
    "yearly":    (400, 730),
}


def age_status(age_days: float | None, cadence: str) -> AgeStatus:
    if age_days is None:
        return "gray"
    if cadence not in _THRESHOLDS:
        return "gray"
    yellow_at, red_at = _THRESHOLDS[cadence]
    if age_days > red_at:
        return "red"
    if age_days > yellow_at:
        return "yellow"
    return "green"
