"""ArcGIS REST FeatureServer download strategy (resultOffset pagination)."""

from __future__ import annotations

import asyncio
import time

import geopandas as gpd
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import ArcGISSource
from ..manifest import append_run, build_entry, utc_now_iso
from .io import layer_exists, logger, remove_layer, save_geodataframe


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def fetch_page(
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


async def download_arcgis_layer(
    client: httpx.AsyncClient,
    source: ArcGISSource,
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

        service_path = source.layer_service_paths[layer_id]
        url = f"{source.base_url}/{service_path}/query"
        logger.info("[%s] Fetching from ArcGIS REST: %s", tag, url)

        acquired_at = utc_now_iso()
        t_start = time.monotonic()

        def _record(status: str, n_features: int = 0, error: str | None = None) -> None:
            append_run(build_entry(
                source, layer_id,
                acquired_at=acquired_at,
                duration_s=time.monotonic() - t_start,
                status=status, endpoint=url,
                n_features=n_features, error=error,
            ))

        all_features: list[dict] = []
        offset = 0
        try:
            while True:
                data = await fetch_page(client, url, offset, source.max_record_count)
                features = data.get("features", [])
                if not features:
                    break
                all_features.extend(features)
                logger.info(
                    "[%s] Fetched %d features (total so far: %d).",
                    tag, len(features), len(all_features),
                )
                if len(features) < source.max_record_count:
                    break
                offset += len(features)
        except Exception as exc:
            logger.exception("[%s] Failed to fetch from ArcGIS.", tag)
            _record("failed", error=repr(exc))
            return

        if not all_features:
            logger.warning("[%s] No features found.", tag)
            _record("empty")
            return

        gdf = gpd.GeoDataFrame.from_features(all_features)
        save_geodataframe(
            gdf, source, layer_id,
            acquired_at=acquired_at, endpoint=url,
        )
        _record("ok", n_features=len(gdf))
