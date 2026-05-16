"""ZIP shapefile download strategy with persistent cache and chunked parquet write."""

from __future__ import annotations

import io as _stdio
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pyogrio

from ..config import ZipShapefileSource
from ..manifest import (
    append_run,
    build_entry,
    footer_metadata,
    utc_now_iso,
)
from .io import (
    CACHE_DIR,
    layer_exists,
    logger,
    parquet_path,
    remove_layer,
)

_ZIP_CHUNK_SIZE = 50_000


def _shapefile_to_parquet(
    shp_path: Path,
    out_path: Path,
    epsg: int,
    *,
    metadata: dict[bytes, bytes],
) -> int:
    """Write shapefile to parquet in chunks to avoid OOM on large files."""
    info = pyogrio.read_info(shp_path)
    feature_count = info["features"]
    writer = None
    total = 0
    t0 = time.monotonic()
    try:
        for offset in range(0, feature_count, _ZIP_CHUNK_SIZE):
            chunk = pyogrio.read_dataframe(
                shp_path,
                skip_features=offset,
                max_features=_ZIP_CHUNK_SIZE,
            )
            if chunk.crs is None:
                chunk.set_crs(epsg=epsg, inplace=True)
            buf = _stdio.BytesIO()
            chunk.to_parquet(buf, index=False)
            buf.seek(0)
            table = pq.read_table(buf)
            if writer is None:
                merged = {**(table.schema.metadata or {}), **metadata}
                writer = pq.ParquetWriter(out_path, table.schema.with_metadata(merged))
            writer.write_table(table)
            total += len(chunk)
            logger.debug(
                "[%s] Written %d/%d features so far...",
                out_path.stem, total, feature_count,
            )
    finally:
        if writer:
            writer.close()
    logger.info(
        "[%s] Parquet written: %d features in %.1fs",
        out_path.stem, total, time.monotonic() - t0,
    )
    return total


def download_zip_layer(source: ZipShapefileSource, reset: bool = False) -> None:
    layer_id = source.name
    out_path = parquet_path(source, layer_id)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zip_cache_path = CACHE_DIR / f"{source.name}.zip"
    zip_partial_path = zip_cache_path.with_suffix(".zip.partial")

    if reset:
        remove_layer(source, layer_id)
        for p in (zip_cache_path, zip_partial_path):
            if p.exists():
                p.unlink()
                logger.info("[%s] Cached ZIP removed: %s", layer_id, p)

    if layer_exists(source, layer_id):
        logger.info("[%s] Parquet already exists, skipping.", layer_id)
        return

    acquired_at = utc_now_iso()
    t_start = time.monotonic()
    endpoint = source.url

    if zip_cache_path.exists():
        logger.info("[%s] Using cached ZIP at %s", layer_id, zip_cache_path)
    else:
        logger.info("[%s] Downloading ZIP from %s ...", layer_id, source.url)
        timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)
        t_dl = time.monotonic()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True, verify=False) as client:
                with client.stream("GET", source.url) as r:
                    r.raise_for_status()
                    with open(zip_partial_path, "wb") as f:
                        for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                            f.write(chunk)
            zip_partial_path.replace(zip_cache_path)
        except Exception as exc:
            logger.exception("[%s] Failed to download ZIP.", layer_id)
            zip_partial_path.unlink(missing_ok=True)
            append_run(build_entry(
                source, layer_id,
                acquired_at=acquired_at,
                duration_s=time.monotonic() - t_start,
                status="failed", endpoint=endpoint, error=repr(exc),
            ))
            return
        size_kb = zip_cache_path.stat().st_size / 1024
        logger.info(
            "[%s] Download complete: %.0f KB in %.1fs (cached at %s)",
            layer_id, size_kb, time.monotonic() - t_dl, zip_cache_path,
        )

    extract_dir = Path(tempfile.mkdtemp(prefix=f"terrasync_{layer_id}_"))
    try:
        with zipfile.ZipFile(zip_cache_path) as zf:
            shp_files = [n for n in zf.namelist() if n.endswith(".shp")]
            if not shp_files:
                logger.error("[%s] No .shp file found in ZIP.", layer_id)
                append_run(build_entry(
                    source, layer_id,
                    acquired_at=acquired_at,
                    duration_s=time.monotonic() - t_start,
                    status="failed", endpoint=endpoint,
                    error="no .shp inside ZIP",
                ))
                return
            zf.extractall(extract_dir)

        shp_path = extract_dir / shp_files[0]
        info = pyogrio.read_info(shp_path)
        feature_count = info["features"]
        metadata = footer_metadata(
            source, layer_id,
            acquired_at=acquired_at, endpoint=endpoint, n_features=feature_count,
        )
        total = _shapefile_to_parquet(shp_path, out_path, source.epsg, metadata=metadata)
        logger.info("[%s] Done: %d features saved to %s.", layer_id, total, out_path)
    except Exception as exc:
        logger.exception("[%s] Failed to convert shapefile to parquet.", layer_id)
        if out_path.exists():
            out_path.unlink()
        append_run(build_entry(
            source, layer_id,
            acquired_at=acquired_at,
            duration_s=time.monotonic() - t_start,
            status="failed", endpoint=endpoint, error=repr(exc),
        ))
        return
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)

    zip_cache_path.unlink(missing_ok=True)
    logger.info("[%s] Cached ZIP removed after successful parquet write.", layer_id)

    append_run(build_entry(
        source, layer_id,
        acquired_at=acquired_at,
        duration_s=time.monotonic() - t_start,
        status="ok", endpoint=endpoint, n_features=total,
    ))
