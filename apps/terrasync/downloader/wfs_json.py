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
    tag = f"{source.name}/{layer_id}"
    params = {
        **wfs_base_params(source, layer_id),
        source.count_param_name(): 1,
    }
    if source.wfs_version >= "2.0.0":
        params["startIndex"] = 0
    r = await client.get(source.effective_base_url(layer_id), params=params)
    r.raise_for_status()
    try:
        total = r.json().get("totalFeatures", 0)
    except json.JSONDecodeError:
        snippet = r.text[:200].replace("\n", " ")
        logger.warning("[%s] Non-JSON response from totalFeatures (snippet: %r)", tag, snippet)
        raise
    logger.debug("[%s] totalFeatures=%d", tag, total)
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
    tag = f"{source.name}/{layer_id}"
    params = {
        **wfs_base_params(source, layer_id),
        **source.pagination_params(source.page_size, start_index),
    }
    chunks: list[bytes] = []
    async with client.stream("GET", source.effective_base_url(layer_id), params=params) as r:
        r.raise_for_status()
        async for chunk in r.aiter_bytes(chunk_size=1024 * 1024):
            chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        snippet = raw[:200].decode("utf-8", errors="replace").replace("\n", " ")
        logger.warning("[%s] Non-JSON page response (snippet: %r)", tag, snippet)
        raise
    features = data.get("features", [])
    if not features:
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame.from_features(features)


@retry(
    retry=retry_if_exception_type(_RETRY_EXC),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def fetch_page_cursor(
    client: httpx.AsyncClient,
    source: WFSSource,
    layer_id: str,
    sort_field: str,
    cursor_value: int | None,
) -> gpd.GeoDataFrame:
    """Cursor-based page fetch for WFS 1.0.0 servers that don't support startIndex.

    Uses CQL_FILTER={sort_field}>{cursor_value} instead of startIndex to advance pages.
    """
    tag = f"{source.name}/{layer_id}"
    params = {
        **wfs_base_params(source, layer_id),
        source.count_param_name(): source.page_size,
    }
    if cursor_value is not None:
        # Numeric fields: uid>12345  |  String/date fields: view_date>'2024-01-01'
        if isinstance(cursor_value, (int, float)):
            params["CQL_FILTER"] = f"{sort_field}>{cursor_value}"
        else:
            params["CQL_FILTER"] = f"{sort_field}>'{cursor_value}'"
    chunks: list[bytes] = []
    async with client.stream("GET", source.effective_base_url(layer_id), params=params) as r:
        r.raise_for_status()
        async for chunk in r.aiter_bytes(chunk_size=1024 * 1024):
            chunks.append(chunk)
    raw = b"".join(chunks)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        snippet = raw[:200].decode("utf-8", errors="replace").replace("\n", " ")
        logger.warning("[%s] Non-JSON cursor page response (snippet: %r)", tag, snippet)
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
    tag = f"{source.name}/{layer_id}"
    async with sem:
        if reset:
            remove_layer(source, layer_id)
        if layer_exists(source, layer_id):
            logger.info("[%s] Parquet already exists, skipping.", tag)
            return

        type_name = source.effective_template(layer_id).format(layer=layer_id)
        endpoint = f"{source.effective_base_url(layer_id)}?typeName={type_name}"
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
            logger.info("[%s] Downloading GML (no pagination)...", tag)
            try:
                gdf = await fetch_gml(client, source, layer_id)
            except Exception as exc:
                logger.exception("[%s] Failed to download GML.", tag)
                _record("failed", error=repr(exc))
                return
            if gdf.empty:
                logger.warning("[%s] No features found.", tag)
                _record("empty")
                return
            logger.info("[%s] %d features received.", tag, len(gdf))
            save_geodataframe(
                gdf, source, layer_id,
                acquired_at=acquired_at, endpoint=endpoint,
            )
            _record("ok", n_features=len(gdf))
            return

        # WFS 1.0.0 servers don't support startIndex — use cursor pagination instead
        # (advances via CQL_FILTER={sort_field}>{last_value} so each page is a fresh request)
        sort_field = source.effective_sort_by(layer_id)
        use_cursor = source.wfs_version < "2.0.0" and sort_field is not None

        if use_cursor:
            logger.info("[%s] Cursor pagination on field '%s'...", tag, sort_field)
            frames: list[gpd.GeoDataFrame] = []
            cursor_value: int | None = None
            page_num = 0
            while True:
                page_num += 1
                logger.info("[%s] Page %d (cursor=%s)...", tag, page_num, cursor_value)
                try:
                    gdf = await fetch_page_cursor(
                        client, source, layer_id, sort_field, cursor_value,
                    )
                except Exception:
                    logger.exception("[%s] Error on cursor page %d.", tag, page_num)
                    break
                if gdf.empty:
                    break
                frames.append(gdf)
                if sort_field not in gdf.columns:
                    logger.error(
                        "[%s] Sort field '%s' missing from response columns %s.",
                        tag, sort_field, list(gdf.columns),
                    )
                    break
                raw_max = gdf[sort_field].max()
                cursor_value = int(raw_max) if pd.api.types.is_numeric_dtype(gdf[sort_field]) else str(raw_max)
                if len(gdf) < source.page_size:
                    break

            if not frames:
                logger.error("[%s] No cursor pages downloaded.", tag)
                _record("failed", error="all cursor pages failed")
                return

            result = pd.concat(frames, ignore_index=True)
            merged = gpd.GeoDataFrame(result)
            save_geodataframe(
                merged, source, layer_id,
                acquired_at=acquired_at, endpoint=endpoint,
            )
            _record("ok", n_features=len(merged))
            return

        logger.info("[%s] Querying total features...", tag)
        try:
            total = await get_total(client, source, layer_id)
        except Exception as exc:
            logger.exception("[%s] Failed to get total features.", tag)
            _record("failed", error=repr(exc))
            return

        if total == 0:
            logger.warning("[%s] No features found.", tag)
            _record("empty")
            return

        total_pages = -(-total // source.page_size)
        logger.info("[%s] %d features — %d page(s).", tag, total, total_pages)

        frames: list[gpd.GeoDataFrame] = []
        for start in range(0, total, source.page_size):
            page_num = start // source.page_size + 1
            logger.info(
                "[%s] Downloading page %d/%d (offset %d)...",
                tag, page_num, total_pages, start,
            )
            try:
                gdf = await fetch_page(client, source, layer_id, start)
                if not gdf.empty:
                    frames.append(gdf)
            except Exception:
                logger.exception("[%s] Error on page %d.", tag, page_num)

        if not frames:
            logger.error("[%s] No pages downloaded successfully.", tag)
            _record("failed", error="all pages failed")
            return

        result = pd.concat(frames, ignore_index=True)
        merged = gpd.GeoDataFrame(result)
        save_geodataframe(
            merged, source, layer_id,
            acquired_at=acquired_at, endpoint=endpoint,
        )
        _record("ok", n_features=len(merged))
