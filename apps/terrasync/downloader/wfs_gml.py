"""GML fetch path for i3geo WFS servers (no JSON output, no pagination).

Used by `incra_sigef_*`, `incra_snci_*`, `incra_assentamentos` — servers that
reply with `ServiceException` to `outputFormat=application/json`.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

import geopandas as gpd
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import WFSSource
from .io import logger


def wfs_base_params(source: WFSSource, layer_id: str) -> dict:
    """WFS GetFeature parameter dict, shared by the JSON and GML paths."""
    params = {
        "service": "WFS",
        "version": source.wfs_version,
        "request": "GetFeature",
        "typeName": source.effective_template(layer_id).format(layer=layer_id),
    }
    if not source.use_gml:
        params["outputFormat"] = "application/json"
    sort_by = source.effective_sort_by(layer_id)
    if sort_by:
        params["sortBy"] = sort_by
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
async def fetch_gml(
    client: httpx.AsyncClient, source: WFSSource, layer_id: str,
) -> gpd.GeoDataFrame:
    params = wfs_base_params(source, layer_id)
    chunks: list[bytes] = []
    t_dl = time.monotonic()
    async with client.stream("GET", source.effective_base_url(layer_id), params=params) as r:
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
