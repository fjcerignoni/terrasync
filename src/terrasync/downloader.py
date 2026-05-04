import asyncio
import logging
import ssl

import httpx
import pandas as pd

from .client import fetch_page, get_total_features
from .config import GeoServerSource

logger = logging.getLogger("terrasync.downloader")


def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _remove_layer(source: GeoServerSource, layer_id: str) -> None:
    output_file = source.output_file
    if not output_file.exists():
        return
    import sqlite3
    con = sqlite3.connect(output_file)
    try:
        tables = [r[0] for r in con.execute(
            "SELECT table_name FROM gpkg_contents WHERE table_name = ?", (layer_id,)
        ).fetchall()]
        if not tables:
            return
        con.execute(f'DROP TABLE IF EXISTS "{layer_id}"')
        con.execute("DELETE FROM gpkg_contents WHERE table_name = ?", (layer_id,))
        con.execute("DELETE FROM gpkg_geometry_columns WHERE table_name = ?", (layer_id,))
        con.execute("DELETE FROM gpkg_ogr_contents WHERE table_name = ?", (layer_id,))
        con.commit()
        con.execute("VACUUM")
        logger.info("[%s] Layer removed from GPKG.", layer_id)
    except Exception:
        logger.exception("[%s] Error removing layer.", layer_id)
    finally:
        con.close()


def _layer_exists(source: GeoServerSource, layer_id: str) -> bool:
    output_file = source.output_file
    if not output_file.exists():
        return False
    import sqlite3
    con = sqlite3.connect(output_file)
    try:
        rows = con.execute(
            "SELECT 1 FROM gpkg_contents WHERE table_name = ?", (layer_id,)
        ).fetchone()
        return rows is not None
    except Exception:
        return False
    finally:
        con.close()


async def _download_layer(
    client: httpx.AsyncClient,
    source: GeoServerSource,
    layer_id: str,
    sem: asyncio.Semaphore,
    reset: bool = False,
) -> None:
    async with sem:
        output_file = source.output_file

        if reset:
            _remove_layer(source, layer_id)

        if _layer_exists(source, layer_id):
            logger.info("[%s] Layer already exists in GPKG, skipping.", layer_id)
            return

        logger.info("[%s] Querying total features...", layer_id)
        try:
            total = await get_total_features(client, source, layer_id)
        except Exception:
            logger.exception("[%s] Failed to get total features.", layer_id)
            return

        if total == 0:
            logger.warning("[%s] No features found.", layer_id)
            return

        total_pages = -(-total // source.page_size)
        logger.info("[%s] %d features — %d page(s).", layer_id, total, total_pages)

        frames = []
        for start in range(0, total, source.page_size):
            page_num = start // source.page_size + 1
            logger.info("[%s] Downloading page %d/%d (offset %d)...", layer_id, page_num, total_pages, start)
            try:
                gdf = await fetch_page(client, source, layer_id, start)
                frames.append(gdf)
            except Exception:
                logger.exception("[%s] Error on page %d.", layer_id, page_num)

        if not frames:
            logger.error("[%s] No pages downloaded successfully.", layer_id)
            return

        result = pd.concat(frames, ignore_index=True)
        result.set_crs(epsg=source.epsg, inplace=True)
        result.to_file(output_file, layer=layer_id, driver="GPKG")
        logger.info("[%s] Done: %d features saved as layer in %s.", layer_id, len(result), output_file)


async def download_all(
    source: GeoServerSource,
    layers: list[str] | None = None,
    reset: bool = False,
) -> None:
    layers = layers or source.layers
    source.output_dir.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(source.max_concurrent)
    limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
    timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)
    ssl_ctx = _make_ssl_context()

    async with httpx.AsyncClient(
        limits=limits, timeout=timeout, follow_redirects=True, verify=ssl_ctx
    ) as client:
        await asyncio.gather(
            *[_download_layer(client, source, layer_id, sem, reset) for layer_id in layers]
        )
