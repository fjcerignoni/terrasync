import logging
import shutil
import ssl
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import httpx

from .config import ShapefileSource

logger = logging.getLogger("terrasync.shapefile_downloader")


def _make_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _layer_exists(source: ShapefileSource, layer_id: str) -> bool:
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


def _remove_layer(source: ShapefileSource, layer_id: str) -> None:
    output_file = source.output_file
    if not output_file.exists():
        return
    import sqlite3

    con = sqlite3.connect(output_file)
    try:
        tables = [
            r[0]
            for r in con.execute(
                "SELECT table_name FROM gpkg_contents WHERE table_name = ?",
                (layer_id,),
            ).fetchall()
        ]
        if not tables:
            return
        con.execute(f'DROP TABLE IF EXISTS "{layer_id}"')
        con.execute("DELETE FROM gpkg_contents WHERE table_name = ?", (layer_id,))
        con.execute(
            "DELETE FROM gpkg_geometry_columns WHERE table_name = ?", (layer_id,)
        )
        con.execute("DELETE FROM gpkg_ogr_contents WHERE table_name = ?", (layer_id,))
        con.commit()
        con.execute("VACUUM")
        logger.info("[%s] Layer removed from GPKG.", layer_id)
    except Exception:
        logger.exception("[%s] Error removing layer.", layer_id)
    finally:
        con.close()


def _download_layer(
    client: httpx.Client,
    source: ShapefileSource,
    layer_id: str,
    reset: bool = False,
) -> None:
    output_file = source.output_file

    if reset:
        _remove_layer(source, layer_id)

    if _layer_exists(source, layer_id):
        logger.info("[%s] Layer already exists in GPKG, skipping.", layer_id)
        return

    url = source.layer_urls[layer_id]
    logger.info("[%s] Downloading ZIP from %s ...", layer_id, url)

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"terrasync_{layer_id}_"))
    zip_path = tmp_dir / "download.zip"
    extract_dir = tmp_dir / "extracted"

    try:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
    except Exception:
        logger.exception("[%s] Failed to download ZIP.", layer_id)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return

    logger.info("[%s] Extracting shapefile from ZIP...", layer_id)
    try:
        with zipfile.ZipFile(zip_path) as zf:
            shp_files = [n for n in zf.namelist() if n.endswith(".shp")]
            if not shp_files:
                logger.error("[%s] No .shp file found in ZIP.", layer_id)
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return
            zf.extractall(extract_dir)

        shp_path = extract_dir / shp_files[0]
        gdf = gpd.read_file(shp_path)
    except Exception:
        logger.exception("[%s] Failed to read shapefile.", layer_id)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return

    if gdf.crs is None:
        gdf.set_crs(epsg=source.epsg, inplace=True)

    gdf.to_file(output_file, layer=layer_id, driver="GPKG")
    logger.info(
        "[%s] Done: %d features saved as layer in %s.",
        layer_id,
        len(gdf),
        output_file,
    )
    shutil.rmtree(tmp_dir, ignore_errors=True)


def download_all(
    source: ShapefileSource,
    layers: list[str] | None = None,
    reset: bool = False,
) -> None:
    layers = layers or source.layers
    source.output_dir.mkdir(exist_ok=True)
    timeout = httpx.Timeout(connect=30.0, read=600.0, write=30.0, pool=30.0)
    ssl_ctx = _make_ssl_context()

    with httpx.Client(
        timeout=timeout, follow_redirects=True, verify=ssl_ctx
    ) as client:
        for layer_id in layers:
            _download_layer(client, source, layer_id, reset)
