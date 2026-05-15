"""Filesystem and SSL helpers shared by every download strategy.

All filesystem side effects of the downloader package live here: writing
parquet, removing layer files, computing canonical paths. Keeping them in
one module avoids hidden side effects scattered across strategy modules.
"""

from __future__ import annotations

import io as _stdio
import logging
import ssl
from pathlib import Path

import geopandas as gpd
import pyarrow.parquet as pq

from ..config import CACHE_DIR, DataSource, source_parquet_path
from ..manifest import footer_metadata

logger = logging.getLogger("terrasync.downloader")

__all__ = [
    "CACHE_DIR",
    "logger",
    "make_ssl_context",
    "parquet_path",
    "layer_exists",
    "remove_layer",
    "save_geodataframe",
]


def make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    except ssl.SSLError as exc:
        logger.warning("Could not relax cipher security level: %s", exc)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def parquet_path(source: DataSource, layer_id: str) -> Path:
    return source_parquet_path(source, layer_id)


def layer_exists(source: DataSource, layer_id: str) -> bool:
    return parquet_path(source, layer_id).exists()


def remove_layer(source: DataSource, layer_id: str) -> None:
    path = parquet_path(source, layer_id)
    if path.exists():
        path.unlink()
        logger.info("[%s] Parquet file removed.", layer_id)


def save_geodataframe(
    gdf: gpd.GeoDataFrame,
    source: DataSource,
    layer_id: str,
    *,
    acquired_at: str,
    endpoint: str,
) -> None:
    if gdf.crs is None:
        gdf.set_crs(epsg=source.epsg, inplace=True)
    out_path = parquet_path(source, layer_id)

    # Roundtrip through an in-memory buffer so geopandas writes its geo schema
    # metadata, then we merge our terrasync.* keys before flushing to disk.
    buf = _stdio.BytesIO()
    gdf.to_parquet(buf)
    buf.seek(0)
    table = pq.read_table(buf)
    extra = footer_metadata(
        source, layer_id,
        acquired_at=acquired_at, endpoint=endpoint, n_features=len(gdf),
    )
    merged = {**(table.schema.metadata or {}), **extra}
    pq.write_table(table.replace_schema_metadata(merged), out_path)
    logger.info("[%s] Done: %d features saved to %s.", layer_id, len(gdf), out_path)
