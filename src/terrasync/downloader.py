import asyncio
import json
import logging
import ssl
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import ArcGISSource, DataSource, WFSSource

logger = logging.getLogger("terrasync.downloader")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _parquet_path(source: DataSource, layer_id: str) -> Path:
    return source.bronze_dir / f"{layer_id}.parquet"


def _layer_exists(source: DataSource, layer_id: str) -> bool:
    return _parquet_path(source, layer_id).exists()


def _remove_layer(source: DataSource, layer_id: str) -> None:
    path = _parquet_path(source, layer_id)
    if path.exists():
        path.unlink()
        logger.info("[%s] Parquet file removed.", layer_id)


def _save_geodataframe(gdf: gpd.GeoDataFrame, source: DataSource, layer_id: str) -> None:
    if gdf.crs is None:
        gdf.set_crs(epsg=source.epsg, inplace=True)
    out_path = _parquet_path(source, layer_id)
    gdf.to_parquet(out_path)
    logger.info("[%s] Done: %d features saved to %s.", layer_id, len(gdf), out_path)


# ---------------------------------------------------------------------------
# WFS strategy
# ---------------------------------------------------------------------------

def _wfs_base_params(source: WFSSource, layer_id: str) -> dict:
    params = {
        "service": "WFS",
        "version": source.wfs_version,
        "request": "GetFeature",
        "typeName": source.layer_template.format(layer=layer_id),
    }
    if not source.use_gml:
        params["outputFormat"] = "application/json"
    if source.sort_by:
        params["sortBy"] = source.sort_by
    if source.extra_params:
        for k, v in source.extra_params.items():
            params[k] = v.format(layer=layer_id)
    return params


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _wfs_get_total(
    client: httpx.AsyncClient, source: WFSSource, layer_id: str,
) -> int:
    params = {
        **_wfs_base_params(source, layer_id),
        source.count_param_name(): 1,
        "startIndex": 0,
    }
    r = await client.get(source.base_url, params=params)
    r.raise_for_status()
    total = r.json().get("totalFeatures", 0)
    logger.debug("[%s] totalFeatures=%d", layer_id, total)
    return total


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _wfs_fetch_page(
    client: httpx.AsyncClient, source: WFSSource, layer_id: str, start_index: int,
) -> gpd.GeoDataFrame:
    params = {
        **_wfs_base_params(source, layer_id),
        **source.pagination_params(source.page_size, start_index),
    }
    chunks: list[bytes] = []
    async with client.stream("GET", source.base_url, params=params) as r:
        r.raise_for_status()
        async for chunk in r.aiter_bytes(chunk_size=1024 * 1024):
            chunks.append(chunk)
    data = json.loads(b"".join(chunks))
    features = data.get("features", [])
    if not features:
        return gpd.GeoDataFrame()
    return gpd.GeoDataFrame.from_features(features)


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _wfs_fetch_gml(
    client: httpx.AsyncClient, source: WFSSource, layer_id: str,
) -> gpd.GeoDataFrame:
    params = _wfs_base_params(source, layer_id)
    chunks: list[bytes] = []
    t_dl = time.monotonic()
    async with client.stream("GET", source.base_url, params=params) as r:
        r.raise_for_status()
        async for chunk in r.aiter_bytes(chunk_size=1024 * 1024):
            chunks.append(chunk)
    content = b"".join(chunks)
    dl_secs = time.monotonic() - t_dl
    size_kb = len(content) / 1024
    logger.info(
        "[%s] Download complete: %.0f KB in %.1fs", layer_id, size_kb, dl_secs
    )
    with tempfile.NamedTemporaryFile(suffix=".gml", delete=False) as f:
        f.write(content)
        tmp_path = f.name
    try:
        t_parse = time.monotonic()
        gdf = gpd.read_file(tmp_path)
        logger.info(
            "[%s] GML parsed: %d features in %.1fs",
            layer_id, len(gdf), time.monotonic() - t_parse,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return gdf


async def _download_wfs_layer(
    client: httpx.AsyncClient,
    source: WFSSource,
    layer_id: str,
    sem: asyncio.Semaphore,
    reset: bool = False,
) -> None:
    async with sem:
        if reset:
            _remove_layer(source, layer_id)
        if _layer_exists(source, layer_id):
            logger.info("[%s] Parquet already exists, skipping.", layer_id)
            return

        if source.use_gml:
            logger.info("[%s] Downloading GML (no pagination)...", layer_id)
            try:
                gdf = await _wfs_fetch_gml(client, source, layer_id)
            except Exception:
                logger.exception("[%s] Failed to download GML.", layer_id)
                return
            if gdf.empty:
                logger.warning("[%s] No features found.", layer_id)
                return
            logger.info("[%s] %d features received.", layer_id, len(gdf))
            _save_geodataframe(gdf, source, layer_id)
            return

        logger.info("[%s] Querying total features...", layer_id)
        try:
            total = await _wfs_get_total(client, source, layer_id)
        except Exception:
            logger.exception("[%s] Failed to get total features.", layer_id)
            return

        if total == 0:
            logger.warning("[%s] No features found.", layer_id)
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
                gdf = await _wfs_fetch_page(client, source, layer_id, start)
                if not gdf.empty:
                    frames.append(gdf)
            except Exception:
                logger.exception("[%s] Error on page %d.", layer_id, page_num)

        if not frames:
            logger.error("[%s] No pages downloaded successfully.", layer_id)
            return

        result = pd.concat(frames, ignore_index=True)
        _save_geodataframe(gpd.GeoDataFrame(result), source, layer_id)


# ---------------------------------------------------------------------------
# ArcGIS REST strategy
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def _arcgis_fetch_page(
    client: httpx.AsyncClient, url: str, offset: int, count: int,
) -> dict:
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": count,
    }
    r = await client.get(url, params=params)
    r.raise_for_status()
    return r.json()


async def _download_arcgis_layer(
    client: httpx.AsyncClient,
    source: ArcGISSource,
    layer_id: str,
    sem: asyncio.Semaphore,
    reset: bool = False,
) -> None:
    async with sem:
        if reset:
            _remove_layer(source, layer_id)
        if _layer_exists(source, layer_id):
            logger.info("[%s] Parquet already exists, skipping.", layer_id)
            return

        service_path = source.layer_service_paths[layer_id]
        url = f"{source.base_url}/{service_path}/query"
        logger.info("[%s] Fetching from ArcGIS REST: %s", layer_id, url)

        all_features: list[dict] = []
        offset = 0
        while True:
            data = await _arcgis_fetch_page(client, url, offset, source.max_record_count)
            features = data.get("features", [])
            if not features:
                break
            all_features.extend(features)
            logger.info("[%s] Fetched %d features (total so far: %d).", layer_id, len(features), len(all_features))
            if len(features) < source.max_record_count:
                break
            offset += len(features)

        if not all_features:
            logger.warning("[%s] No features found.", layer_id)
            return

        gdf = gpd.GeoDataFrame.from_features(all_features)
        _save_geodataframe(gdf, source, layer_id)


# ---------------------------------------------------------------------------
# Unified entrypoint
# ---------------------------------------------------------------------------

async def download_all(
    source: DataSource,
    layers: list[str] | None = None,
    reset: bool = False,
) -> None:
    source.bronze_dir.mkdir(parents=True, exist_ok=True)
    ssl_ctx = _make_ssl_context()
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)

    if isinstance(source, WFSSource):
        layer_ids = layers or source.layer_ids
        sem = asyncio.Semaphore(source.max_concurrent)
        async with httpx.AsyncClient(
            limits=limits, timeout=timeout, follow_redirects=True, verify=ssl_ctx,
        ) as client:
            await asyncio.gather(
                *[_download_wfs_layer(client, source, lid, sem, reset) for lid in layer_ids]
            )

    elif isinstance(source, ArcGISSource):
        layer_ids = layers or source.layer_ids
        sem = asyncio.Semaphore(source.max_concurrent)
        async with httpx.AsyncClient(
            limits=limits, timeout=timeout, follow_redirects=True, verify=ssl_ctx,
        ) as client:
            await asyncio.gather(
                *[_download_arcgis_layer(client, source, lid, sem, reset) for lid in layer_ids]
            )
