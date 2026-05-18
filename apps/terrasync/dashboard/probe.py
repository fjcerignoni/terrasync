"""Liveness probe for upstream endpoints (WFS / ArcGIS / ZIP).

Strategy is per source.type:
    - wfs:    GET ?service=WFS&request=GetCapabilities, expect 200 + XML
    - arcgis: GET ?f=json, expect 200 + JSON with currentVersion/serviceDescription
    - zip:    HEAD (fallback GET), accept 2xx/3xx of any Content-Type

States:
    up      — 2xx + payload sanity + latency < SLOW_LATENCY_MS
    slow    — 2xx + payload sanity + latency >= SLOW_LATENCY_MS
    down    — timeout, 4xx, 5xx, TLS/DNS error
    unknown — strategy has no probe (escape hatch)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

import httpx

from ..config import ArcGISSource, DataSource, WFSSource, ZipShapefileSource
from ..downloader.io import make_ssl_context

ProbeStatus = Literal["up", "slow", "down", "unknown"]

SLOW_LATENCY_MS = 3000
TIMEOUT_S = 8.0


@dataclass
class ProbeResult:
    status: ProbeStatus
    http_code: int | None
    latency_ms: int | None
    error: str | None
    checked_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _classify(latency_ms: int) -> ProbeStatus:
    return "slow" if latency_ms >= SLOW_LATENCY_MS else "up"


async def _probe_wfs(client: httpx.AsyncClient, source: WFSSource) -> ProbeResult:
    params = {"service": "WFS", "request": "GetCapabilities"}
    t0 = time.perf_counter()
    try:
        r = await client.get(source.base_url, params=params, timeout=TIMEOUT_S)
    except Exception as e:
        return ProbeResult("down", None, None, f"{type(e).__name__}: {e}", _now())
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        return ProbeResult("down", r.status_code, latency, f"HTTP {r.status_code}", _now())
    body = r.text[:4096].lower()
    if "wfs_capabilities" not in body and "<wfs" not in body:
        return ProbeResult("down", r.status_code, latency, "no WFS_Capabilities", _now())
    return ProbeResult(_classify(latency), r.status_code, latency, None, _now())


async def _probe_arcgis(client: httpx.AsyncClient, source: ArcGISSource) -> ProbeResult:
    # Probe the first layer service path (more reliable than the root URL,
    # which doesn't always honor ?f=json on every server config).
    if source.layers and source.layers[0].service_path:
        url = f"{source.base_url.rstrip('/')}/{source.layers[0].service_path}"
    else:
        url = source.base_url
    t0 = time.perf_counter()
    try:
        r = await client.get(url, params={"f": "json"}, timeout=TIMEOUT_S)
    except Exception as e:
        return ProbeResult("down", None, None, f"{type(e).__name__}: {e}", _now())
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        return ProbeResult("down", r.status_code, latency, f"HTTP {r.status_code}", _now())
    try:
        payload = r.json()
    except Exception:
        return ProbeResult("down", r.status_code, latency, "non-JSON body", _now())
    if "currentVersion" not in payload and "serviceDescription" not in payload and "type" not in payload:
        err = payload.get("error", {}).get("message", "no ArcGIS metadata")
        return ProbeResult("down", r.status_code, latency, err, _now())
    return ProbeResult(_classify(latency), r.status_code, latency, None, _now())


async def _probe_zip(client: httpx.AsyncClient, source: ZipShapefileSource) -> ProbeResult:
    t0 = time.perf_counter()
    try:
        r = await client.head(source.url, timeout=TIMEOUT_S, follow_redirects=True)
        if r.status_code >= 400 or r.status_code == 405:
            # Fallback: some servers don't support HEAD. Stream a tiny GET.
            r = await client.get(
                source.url,
                timeout=TIMEOUT_S,
                follow_redirects=True,
                headers={"Range": "bytes=0-0"},
            )
    except Exception as e:
        return ProbeResult("down", None, None, f"{type(e).__name__}: {e}", _now())
    latency = int((time.perf_counter() - t0) * 1000)
    if r.status_code >= 400:
        return ProbeResult("down", r.status_code, latency, f"HTTP {r.status_code}", _now())
    return ProbeResult(_classify(latency), r.status_code, latency, None, _now())


async def probe(client: httpx.AsyncClient, source: DataSource) -> ProbeResult:
    if isinstance(source, WFSSource):
        return await _probe_wfs(client, source)
    if isinstance(source, ArcGISSource):
        return await _probe_arcgis(client, source)
    if isinstance(source, ZipShapefileSource):
        return await _probe_zip(client, source)
    return ProbeResult("unknown", None, None, "no probe strategy", _now())


async def _probe_all_async(sources: list[DataSource]) -> dict[str, ProbeResult]:
    ssl_ctx = make_ssl_context()
    async with httpx.AsyncClient(verify=ssl_ctx, follow_redirects=True) as client:
        results = await asyncio.gather(
            *[probe(client, s) for s in sources], return_exceptions=True
        )
    out: dict[str, ProbeResult] = {}
    for src, res in zip(sources, results):
        if isinstance(res, BaseException):
            out[src.name] = ProbeResult(
                "down", None, None, f"{type(res).__name__}: {res}", _now()
            )
        else:
            out[src.name] = res
    return out


def probe_all(sources: list[DataSource]) -> dict[str, ProbeResult]:
    """Sync entrypoint for Streamlit (which manages its own event loop)."""
    return asyncio.run(_probe_all_async(sources))
