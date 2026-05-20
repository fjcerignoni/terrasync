"""Downloader genérico para fontes CSV com lat/lon (ex.: NASA FIRMS)."""

from __future__ import annotations

import io as _io
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..config import CsvApiSource, source_parquet_path
from .io import save_geodataframe

_log = logging.getLogger("terrasync.downloader.csv_api")


def _chunk_path(source: CsvApiSource, layer_id: str, chunk_start: date) -> Path:
    return source.rawdata_dir / f"{source.name}_{layer_id}_{chunk_start.isoformat()}.parquet"


def _iter_chunks(start: date, end: date, chunk_days: int):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=chunk_days)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return True


@retry(
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    retry=retry_if_exception(_is_retryable),
)
def _fetch_csv(url: str) -> str:
    resp = httpx.get(url, timeout=60, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _to_geodataframe(df: pd.DataFrame, source: CsvApiSource) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[source.lon_col], df[source.lat_col]),
        crs="EPSG:4326",
    )


def download_csv_api_source(
    source: CsvApiSource,
    layer_ids: list[str],
    reset: bool,
) -> None:
    source.rawdata_dir.mkdir(parents=True, exist_ok=True)

    if reset:
        for f in source.rawdata_dir.glob("*.parquet"):
            f.unlink()
        _log.info("[%s] Reset: parquets removidos.", source.name)

    api_key = os.environ[source.api_key_env] if source.api_key_env else ""

    for layer_id in layer_ids:
        if source.temporal:
            start = date.fromisoformat(source.start_date)
            today = date.today()
            for chunk_start in _iter_chunks(start, today, source.chunk_days):
                out = _chunk_path(source, layer_id, chunk_start)
                if out.exists() and not reset:
                    continue
                url = source.url_template.format(
                    api_key=api_key,
                    date=chunk_start.isoformat(),
                    chunk_days=source.chunk_days,
                )
                _log.info("[%s] Fetching chunk %s → %s", layer_id, chunk_start, out.name)
                try:
                    csv_text = _fetch_csv(url)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 400:
                        _log.warning(
                            "[%s] Chunk %s fora do arquivo NRT (400), pulando.",
                            layer_id, chunk_start,
                        )
                        continue
                    raise
                df = pd.read_csv(_io.StringIO(csv_text))
                if df.empty or source.lat_col not in df.columns:
                    gpd.GeoDataFrame(columns=["geometry"]).to_parquet(out)
                    _log.info("[%s] Chunk %s vazio, marcado.", layer_id, chunk_start)
                    continue
                gdf = _to_geodataframe(df, source)
                save_geodataframe(
                    gdf, source, layer_id,
                    acquired_at=chunk_start.isoformat(),
                    endpoint=url,
                    out_path=out,
                )
        else:
            url = source.url_template.format(api_key=api_key)
            out = source_parquet_path(source, layer_id)
            _log.info("[%s] Fetching %s", layer_id, url)
            csv_text = _fetch_csv(url)
            df = pd.read_csv(_io.StringIO(csv_text))
            gdf = _to_geodataframe(df, source)
            save_geodataframe(
                gdf, source, layer_id,
                acquired_at=date.today().isoformat(),
                endpoint=url,
            )
