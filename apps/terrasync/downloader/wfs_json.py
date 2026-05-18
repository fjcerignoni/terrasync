"""WFS JSON pagination + per-layer WFS download dispatcher.

`download_wfs_layer` is the per-layer entrypoint for WFS sources: it dispatches
between the GML branch (i3geo, no pagination) and the paginated JSON branch.
The base parameter builder lives in :mod:`wfs_gml` to avoid a circular import.
"""

from __future__ import annotations

import asyncio
import json
import time

import geopandas as gpd
import httpx
import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import WFSSource
from ..manifest import append_run, build_entry, utc_now_iso
from .io import layer_exists, logger, remove_layer, save_geodataframe
from .wfs_gml import fetch_gml, wfs_base_params


_RETRY_EXC = (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError)


@retry(
    retry=retry_if_exception_type(_RETRY_EXC),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def get_total(
    client: httpx.AsyncClient, source: WFSSource, layer_id: str,
) -> int:
    params = {
        **wfs_base_params(source, layer_id),
        source.count_param_name(): 1,
        "startIndex": 0,
    }
    r = await client.get(source.base_url, params=params)
    r.raise_for_status()
    try:
        total = r.json().get("totalFeatures", 0)
    except json.JSONDecodeError:
        snippet = r.text[:200].replace("\n", " ")
        logger.warning("[%s] Non-JSON response from totalFeatures (snippet: %r)", layer_id, snippet)
        raise
    logger.debug("[%s] totalFeatures=%d", layer_id, total)
    return total


@retry(
    retry=retry_if_exception_type(_RETRY_EXC),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def fetch_page(
    client: httpx.AsyncClient, source: WFSSource, layer_id: str, start_index: int,
) -> gpd.GeoDataFrame:
    params = {
        **wfs_base_params(source, layer_id),
        **source.pagination_params(source.page_size, start_index),
    }
    chunks: list[bytes] = []
    async with client.stream("GET", source.base_url, params=params) as r:
        r.raise_for_status()
        async for chunk in r.aiter_bytes(chunk_size=1024 * 1024):
            chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        snippet = raw[:200].decode("utf-8", errors="replace").replace("\n", " ")
        logger.warning("[%s] Non-JSON page response (snippet: %r)", layer_id, snippet)
        raise
    features = data.get("features", [])
    if not features:
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame.from_features(features)


async def download_wfs_layer(
    client: httpx.AsyncClient,
    source: WFSSource,
    layer_id: str,
    sem: asyncio.Semaphore,
    reset: bool = False,
) -> None:
    async with sem:
        if reset:
            remove_layer(source, layer_id)
        if layer_exists(source, layer_id):
            logger.info("[%s] Parquet already exists, skipping.", layer_id)
            return

        type_name = source.layer_template.format(layer=layer_id)
        endpoint = f"{source.base_url}?typeName={type_name}"
        acquired_at = utc_now_iso()
        t_start = time.monotonic()

        def _record(status: str, n_features: int = 0, error: str | None = None) -> None:
            append_run(build_entry(
                source, layer_id,
                acquired_at=acquired_at,
                duration_s=time.monotonic() - t_start,
                status=status, endpoint=endpoint,
                n_features=n_features, error=error,
            ))

        if source.use_gml:
            logger.info("[%s] Downloading GML (no pagination)...", layer_id)
            try:
                gdf = await fetch_gml(client, source, layer_id)
            except Exception as exc:
                logger.exception("[%s] Failed to download GML.", layer_id)
                _record("failed", error=repr(exc))
                return
            if gdf.empty:
                logger.warning("[%s] No features found.", layer_id)
                _record("empty")
                return
            logger.info("[%s] %d features received.", layer_id, len(gdf))
            save_geodataframe(
                gdf, source, layer_id,
                acquired_at=acquired_at, endpoint=endpoint,
            )
            _record("ok", n_features=len(gdf))
            return

        logger.info("[%s] Querying total features...", layer_id)
        try:
            total = await get_total(client, source, layer_id)
        except Exception as exc:
            logger.exception("[%s] Failed to get total features.", layer_id)
            _record("failed", error=repr(exc))
            return

        if total == 0:
            logger.warning("[%s] No features found.", layer_id)
            _record("empty")
            return

        total_pages = -(-total // source.page_size)
        logger.info("[%s] %d features — %d page(s).", layer_id, total, total_pages)

        frames: list[gpd.GeoDataFrame] = []
        for start in range(0, total, source.page_size):
            page_num = start // source.page_size + 1
            logger.info(
                "[%s] Downloading page %d/%d (offset %d)...",
                layer_id, page_num, total_pages, start,
            )
            try:
                gdf = await fetch_page(client, source, layer_id, start)
                if not gdf.empty:
                    frames.append(gdf)
            except Exception:
                logger.exception("[%s] Error on page %d.", layer_id, page_num)

        if not frames:
            logger.error("[%s] No pages downloaded successfully.", layer_id)
            _record("failed", error="all pages failed")
            return

        result = pd.concat(frames, ignore_index=True)
        merged = gpd.GeoDataFrame(result)
        save_geodataframe(
            merged, source, layer_id,
            acquired_at=acquired_at, endpoint=endpoint,
        )
        _record("ok", n_features=len(merged))
