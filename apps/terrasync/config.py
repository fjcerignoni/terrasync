from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .paths import DATA_DIR, DBT_DIR

RAWDATA_DIR = DATA_DIR / "rawdata"
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


class ProviderConfig(BaseModel):
    display_name: str


class LayerMeta(BaseModel):
    id: str
    name: str | None = None
    geometry_type: str = "MultiPolygon"
    temporal: bool = False
    service_path: str | None = None  # ArcGIS only
    # Per-layer WFS overrides
    base_url: str | None = None
    layer_template: str | None = None
    sort_by: str | None = None
    # Per-layer ZIP override
    url: str | None = None


Cadence = Literal["daily", "weekly", "monthly", "quarterly", "yearly", "unknown"]


class WFSSource(BaseModel):
    type: Literal["wfs"] = "wfs"
    name: str = ""
    display_name: str = ""
    description: str = ""
    category: str = "boundaries"
    provider: str | None = None
    temporal: bool = False
    cadence: Cadence = "unknown"
    base_url: str | None = None
    layer_template: str | None = None
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
    def rawdata_dir(self) -> Path:
        return RAWDATA_DIR / self.name

    @property
    def layer_ids(self) -> list[str]:
        return [layer.id for layer in self.layers]

    def effective_base_url(self, layer_id: str) -> str:
        layer = next((l for l in self.layers if l.id == layer_id), None)
        if layer and layer.base_url:
            return layer.base_url
        if self.base_url:
            return self.base_url
        raise ValueError(f"No base_url configured for layer {layer_id!r} in source {self.name!r}")

    def effective_template(self, layer_id: str) -> str:
        layer = next((l for l in self.layers if l.id == layer_id), None)
        if layer and layer.layer_template:
            return layer.layer_template
        if self.layer_template:
            return self.layer_template
        raise ValueError(f"No layer_template configured for layer {layer_id!r} in source {self.name!r}")

    def effective_sort_by(self, layer_id: str) -> str | None:
        layer = next((l for l in self.layers if l.id == layer_id), None)
        if layer and layer.sort_by:
            return layer.sort_by
        return self.sort_by

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
    provider: str | None = None
    cadence: Cadence = "unknown"
    base_url: str
    layers: list[LayerMeta]
    max_record_count: int = 1000
    max_concurrent: int = 2
    epsg: int = 4674

    @property
    def rawdata_dir(self) -> Path:
        return RAWDATA_DIR / self.name

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
    provider: str | None = None
    cadence: Cadence = "unknown"
    epsg: int = 4674
    url: str | None = None
    layers: list[LayerMeta] = Field(default_factory=list)
    manual: bool = False
    encoding: str | None = None

    @property
    def rawdata_dir(self) -> Path:
        return RAWDATA_DIR / self.name

    @property
    def layer_ids(self) -> list[str]:
        return [l.id for l in self.layers]

    def effective_url(self, layer_id: str) -> str:
        layer = next((l for l in self.layers if l.id == layer_id), None)
        if layer and layer.url:
            return layer.url
        if self.url:
            return self.url
        raise ValueError(f"No url configured for layer {layer_id!r} in source {self.name!r}")


DataSource = WFSSource | ArcGISSource | ZipShapefileSource


def source_parquet_path(source: "DataSource", layer_id: str) -> Path:
    """Canonical rawdata path for a layer's parquet."""
    return source.rawdata_dir / f"{source.name}_{layer_id}.parquet"


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

    providers: dict[str, ProviderConfig] = {
        k: ProviderConfig(**v) for k, v in raw.get("providers", {}).items()
    }

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

    # Auto-generate source groups from provider membership
    provider_sources: dict[str, list[str]] = {}
    for src_name, src in sources.items():
        p = getattr(src, "provider", None)
        if p:
            provider_sources.setdefault(p, []).append(src_name)

    groups: dict[str, SourceGroup] = {
        p_key: SourceGroup(
            key=p_key,
            name=providers[p_key].display_name if p_key in providers else p_key,
            sources=src_list,
        )
        for p_key, src_list in provider_sources.items()
    }

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
