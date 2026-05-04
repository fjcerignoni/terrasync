from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeoServerSource:
    """Configuration for a GeoServer-based data source."""

    name: str
    base_url: str
    layer_template: str
    layers: list[str]
    output_dir: Path = Path("data")
    page_size: int = 10_000
    max_concurrent: int = 3
    epsg: int = 4674
    sort_by: str | None = None

    @property
    def output_file(self) -> Path:
        return self.output_dir / f"{self.name}.gpkg"


@dataclass
class ShapefileSource:
    """Configuration for a source that provides shapefile ZIPs for download."""

    name: str
    layer_urls: dict[str, str]
    output_dir: Path = Path("data")
    epsg: int = 4674

    @property
    def layers(self) -> list[str]:
        return list(self.layer_urls)

    @property
    def output_file(self) -> Path:
        return self.output_dir / f"{self.name}.gpkg"


DataSource = GeoServerSource | ShapefileSource


SICAR = GeoServerSource(
    name="SICAR",
    base_url="https://geoserver.car.gov.br/geoserver/sicar/ows",
    layer_template="sicar:sicar_imoveis_{layer}",
    layers=[
        "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go",
        "ma", "mg", "ms", "mt", "pa", "pb", "pe", "pi", "pr",
        "rj", "rn", "ro", "rr", "rs", "sc", "se", "sp", "to",
    ],
)

FUNAI = GeoServerSource(
    name="Funai",
    base_url="https://geoserver.funai.gov.br/geoserver/Funai/ows",
    layer_template="Funai:{layer}",
    layers=["tis_poligonais"],
    sort_by="gid",
)

INCRA = ShapefileSource(
    name="Incra",
    layer_urls={
        "quilombolas": "https://certificacao.incra.gov.br/csv_shp/zip/%C3%81reas%20de%20Quilombolas.zip",
        "assentamentos": "https://certificacao.incra.gov.br/csv_shp/zip/Assentamento%20Brasil.zip",
        "sigef_publico": "https://certificacao.incra.gov.br/csv_shp/zip/Sigef%20P%C3%BAblico.zip",
        "sigef_privado": "https://certificacao.incra.gov.br/csv_shp/zip/Sigef%20Privado.zip",
        "snci_publico": "https://certificacao.incra.gov.br/csv_shp/zip/Im%C3%B3vel%20certificado%20SNCI%20P%C3%BAblico.zip",
        "snci_privado": "https://certificacao.incra.gov.br/csv_shp/zip/Im%C3%B3vel%20certificado%20SNCI%20Privado.zip",
    },
)

SOURCES: dict[str, DataSource] = {
    "sicar": SICAR,
    "funai": FUNAI,
    "incra": INCRA,
}
