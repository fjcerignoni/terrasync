"""Top-level dispatchers: route a `DataSource` to its strategy module."""

from __future__ import annotations

import asyncio

import httpx

from ..config import ArcGISSource, CsvApiSource, CsvManualSource, DataSource, WFSSource, ZipShapefileSource
from .arcgis import download_arcgis_layer
from .io import make_ssl_context
from .wfs_json import download_wfs_layer
from .zip_shp import download_zip_layer


def _httpx_defaults() -> tuple[httpx.Limits, httpx.Timeout]:
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)
    return limits, timeout


async def download_all(
    source: DataSource,
    layers: list[str] | None = None,
    reset: bool = False,
) -> None:
    """Download every requested layer of `source` to rawdata parquet."""
    source.rawdata_dir.mkdir(parents=True, exist_ok=True)
    ssl_ctx = make_ssl_context()
    limits, timeout = _httpx_defaults()

    if isinstance(source, WFSSource):
        layer_ids = layers or source.layer_ids
        sem = asyncio.Semaphore(source.max_concurrent)
        async with httpx.AsyncClient(
            limits=limits, timeout=timeout, follow_redirects=True, verify=ssl_ctx,
        ) as client:
            await asyncio.gather(
                *[download_wfs_layer(client, source, lid, sem, reset) for lid in layer_ids]
            )

    elif isinstance(source, ArcGISSource):
        layer_ids = layers or source.layer_ids
        sem = asyncio.Semaphore(source.max_concurrent)
        async with httpx.AsyncClient(
            limits=limits, timeout=timeout, follow_redirects=True, verify=ssl_ctx,
        ) as client:
            await asyncio.gather(
                *[download_arcgis_layer(client, source, lid, sem, reset) for lid in layer_ids]
            )

    elif isinstance(source, ZipShapefileSource):
        layer_ids = layers or source.layer_ids
        for lid in layer_ids:
            await asyncio.to_thread(download_zip_layer, source, lid, reset)

    elif isinstance(source, CsvApiSource):
        from .csv_api import download_csv_api_source
        await asyncio.to_thread(
            download_csv_api_source, source, layers or source.layer_ids, reset
        )

    elif isinstance(source, CsvManualSource):
        from .csv_manual import ingest_csv_manual
        for lid in (layers or source.layer_ids):
            await asyncio.to_thread(ingest_csv_manual, source, lid, reset)


async def download_layer(
    source: DataSource,
    layer_id: str,
    reset: bool = False,
) -> None:
    """Download a single layer of `source`. Thin wrapper over `download_all`."""
    await download_all(source, layers=[layer_id], reset=reset)
