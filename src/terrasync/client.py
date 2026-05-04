import json
import logging

import geopandas as gpd
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import GeoServerSource

logger = logging.getLogger("terrasync.client")


def _base_params(source: GeoServerSource, layer_id: str) -> dict:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": source.layer_template.format(layer=layer_id),
        "outputFormat": "application/json",
    }
    if source.sort_by:
        params["sortBy"] = source.sort_by
    return params


@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def get_total_features(
    client: httpx.AsyncClient, source: GeoServerSource, layer_id: str
) -> int:
    params = {**_base_params(source, layer_id), "count": 1, "startIndex": 0}
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
async def fetch_page(
    client: httpx.AsyncClient,
    source: GeoServerSource,
    layer_id: str,
    start_index: int,
) -> gpd.GeoDataFrame:
    params = {
        **_base_params(source, layer_id),
        "count": source.page_size,
        "startIndex": start_index,
    }
    chunks: list[bytes] = []
    async with client.stream("GET", source.base_url, params=params) as r:
        r.raise_for_status()
        async for chunk in r.aiter_bytes(chunk_size=1024 * 1024):
            chunks.append(chunk)
    return gpd.GeoDataFrame.from_features(json.loads(b"".join(chunks))["features"])
