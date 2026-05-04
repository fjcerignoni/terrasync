import logging

import geopandas as gpd
from shapely import make_valid
from shapely import get_parts
from shapely import Polygon, MultiPolygon

from .config import DataSource

logger = logging.getLogger("terrasync.processor")

GEO_BOUNDS = (-180.0, -90.0, 180.0, 90.0)

PROCESSED_SUFFIX = "_processed"


def _within_bounds(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    min_lon, min_lat, max_lon, max_lat = GEO_BOUNDS
    bounds = gdf.geometry.bounds
    mask = (
        (bounds["minx"] >= min_lon)
        & (bounds["miny"] >= min_lat)
        & (bounds["maxx"] <= max_lon)
        & (bounds["maxy"] <= max_lat)
    )
    removed = (~mask).sum()
    if removed:
        logger.warning("Removed %d features outside geographic bounds.", removed)
    return gdf[mask].copy()


def _extract_polygons(geom):
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    parts = [p for p in get_parts(geom) if isinstance(p, Polygon)]
    if not parts:
        return None
    return MultiPolygon(parts) if len(parts) > 1 else parts[0]


def _fix_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    invalid = ~gdf.geometry.is_valid
    n_invalid = invalid.sum()
    if n_invalid:
        logger.info("Fixing %d invalid geometries with make_valid.", n_invalid)
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].apply(make_valid)
        gdf["geometry"] = gdf["geometry"].apply(_extract_polygons)
        gdf = gdf[gdf.geometry.notna()].copy()
    return gdf


def process_layer(source: DataSource, layer_id: str) -> None:
    layer_out = f"{layer_id}{PROCESSED_SUFFIX}"
    output_file = source.output_file

    logger.info("[%s] Reading raw layer...", layer_id)
    gdf = gpd.read_file(output_file, layer=layer_id)
    total_original = len(gdf)
    logger.info("[%s] %d features read.", layer_id, total_original)

    gdf = _within_bounds(gdf)
    gdf = _fix_geometries(gdf)

    if gdf.crs is None:
        gdf.set_crs(epsg=source.epsg, inplace=True)

    logger.info("[%s] Saving layer '%s' with %d features (from %d original).",
                layer_id, layer_out, len(gdf), total_original)
    gdf.to_file(output_file, layer=layer_out, driver="GPKG")
    logger.info("[%s] Processing complete.", layer_id)


def process_all(source: DataSource, layers: list[str] | None = None) -> None:
    layers = layers or source.layers
    for layer_id in layers:
        try:
            process_layer(source, layer_id)
        except Exception:
            logger.exception("[%s] Error during processing.", layer_id)
