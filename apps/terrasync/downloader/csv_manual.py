"""Ingestor para fontes CSV manuais — lê CSV de data/cache/, cria geometria lat/lon."""

from __future__ import annotations

import logging
from datetime import date

import geopandas as gpd
import pandas as pd

from ..config import CACHE_DIR, CsvManualSource, source_parquet_path
from .io import save_geodataframe

_log = logging.getLogger("terrasync.downloader.csv_manual")


def ingest_csv_manual(source: CsvManualSource, layer_id: str, reset: bool) -> None:
    out = source_parquet_path(source, layer_id)

    if out.exists() and not reset:
        _log.info("[%s/%s] Parquet já existe (use --reset para regravar).", source.name, layer_id)
        return

    pattern = f"{source.name}_*.csv"
    csv_files = sorted(CACHE_DIR.glob(pattern))
    if not csv_files:
        raise FileNotFoundError(
            f"Nenhum CSV encontrado em {CACHE_DIR} com padrão '{pattern}'. "
            f"Baixe manualmente e coloque em {CACHE_DIR}."
        )

    frames = [pd.read_csv(p, dtype={source.lat_col: float, source.lon_col: float}) for p in csv_files]
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df[source.lon_col], df[source.lat_col]),
        crs=f"EPSG:{source.epsg}",
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    save_geodataframe(
        gdf, source, layer_id,
        acquired_at=date.today().isoformat(),
        endpoint=str(csv_files[-1]),
    )
    _log.info("[%s/%s] → %s (%d pontos).", source.name, layer_id, out.name, len(gdf))
