from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .paths import DATA_DIR, DBT_DIR

BRONZE_DIR = DATA_DIR / "bronze"
STAGING_DIR = DATA_DIR / "staging"
CACHE_DIR = DATA_DIR / "cache"
MANIFESTS_DIR = DATA_DIR / "manifests"
DUCKDB_PATH = DATA_DIR / "terrasync.duckdb"
DBT_PROJECT_DIR = DBT_DIR

_SOURCES_YAML = Path(__file__).parent / "sources.yaml"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LayerMeta(BaseModel):
    id: str
    name: str | None = None
    geometry_type: str = "MultiPolygon"
    temporal: bool = False
    service_path: str | None = None  # ArcGIS only


Cadence = Literal["daily", "weekly", "monthly", "quarterly", "yearly", "unknown"]


class WFSSource(BaseModel):
    type: Literal["wfs"] = "wfs"
    name: str = ""
    display_name: str = ""
    description: str = ""
    category: str = "boundaries"
    group: str | None = None
    temporal: bool = False
    cadence: Cadence = "unknown"
    base_url: str
    layer_template: str
    layers: list[LayerMeta]
    wfs_version: str = "2.0.0"
    page_size: int = 10_000
    max_concurrent: int = 3
    epsg: int = 4674
    sort_by: str | None = None
    extra_params: dict[str, str] | None = None
    geometry_type: str = "MultiPolygon"
    use_gml: bool = False

    @property
    def bronze_dir(self) -> Path:
        if self.group and self.group != self.name:
            return BRONZE_DIR / self.group
        return BRONZE_DIR / self.name

    @property
    def layer_ids(self) -> list[str]:
        return [layer.id for layer in self.layers]

    def pagination_params(self, count: int, start: int) -> dict[str, int]:
        if self.wfs_version >= "2.0.0":
            return {"count": count, "startIndex": start}
        return {"maxFeatures": count, "startIndex": start}

    def count_param_name(self) -> str:
        return "count" if self.wfs_version >= "2.0.0" else "maxFeatures"


class ArcGISSource(BaseModel):
    type: Literal["arcgis"] = "arcgis"
    name: str = ""
    display_name: str = ""
    description: str = ""
    category: str = "boundaries"
    group: str | None = None
    cadence: Cadence = "unknown"
    base_url: str
    layers: list[LayerMeta]
    max_record_count: int = 1000
    max_concurrent: int = 2
    epsg: int = 4674

    @property
    def bronze_dir(self) -> Path:
        if self.group and self.group != self.name:
            return BRONZE_DIR / self.group
        return BRONZE_DIR / self.name

    @property
    def layer_ids(self) -> list[str]:
        return [layer.id for layer in self.layers]

    @property
    def layer_service_paths(self) -> dict[str, str]:
        return {l.id: l.service_path for l in self.layers if l.service_path}


class ZipShapefileSource(BaseModel):
    type: Literal["zip_shapefile"] = "zip_shapefile"
    name: str = ""
    display_name: str = ""
    description: str = ""
    category: str = "boundaries"
    group: str | None = None
    cadence: Cadence = "unknown"
    epsg: int = 4674
    url: str

    @property
    def bronze_dir(self) -> Path:
        if self.group and self.group != self.name:
            return BRONZE_DIR / self.group
        return BRONZE_DIR / self.name

    @property
    def layer_ids(self) -> list[str]:
        return [self.name]


DataSource = WFSSource | ArcGISSource | ZipShapefileSource


def source_parquet_path(source: "DataSource", layer_id: str) -> Path:
    """Canonical path of a layer's parquet inside bronze_dir."""
    if layer_id == source.name:
        return source.bronze_dir / f"{layer_id}.parquet"
    return source.bronze_dir / f"{source.name}_{layer_id}.parquet"


class SourceGroup(BaseModel):
    key: str = ""
    name: str = ""
    description: str = ""
    sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def _load_catalog(
    yaml_path: Path = _SOURCES_YAML,
) -> tuple[dict[str, DataSource], dict[str, SourceGroup]]:
    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    sources: dict[str, DataSource] = {}
    for key, cfg in raw.get("sources", {}).items():
        src_type = cfg.get("type")
        if src_type == "wfs":
            src = WFSSource(**cfg)
        elif src_type == "arcgis":
            src = ArcGISSource(**cfg)
        elif src_type == "zip_shapefile":
            src = ZipShapefileSource(**cfg)
        else:
            raise ValueError(f"Unknown source type: {src_type} for {key}")
        src.name = key
        sources[key] = src

    groups: dict[str, SourceGroup] = {}
    for key, gcfg in raw.get("groups", {}).items():
        grp = SourceGroup(key=key, **gcfg)
        groups[key] = grp

    return sources, groups


SOURCES, SOURCE_GROUPS = _load_catalog()


def resolve_sources(source_arg: str) -> list[DataSource]:
    """Resolve a --source argument to a list of DataSource instances."""
    if source_arg == "all":
        return list(SOURCES.values())
    if source_arg in SOURCE_GROUPS:
        return [SOURCES[k] for k in SOURCE_GROUPS[source_arg].sources]
    if source_arg in SOURCES:
        return [SOURCES[source_arg]]
    raise KeyError(f"Unknown source or group: {source_arg}")
