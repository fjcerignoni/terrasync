from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path("data")
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
DUCKDB_PATH = DATA_DIR / "terrasync.duckdb"
DBT_PROJECT_DIR = Path(".")

UF_LAYERS = [
    "ac", "al", "am", "ap", "ba", "ce", "df", "es", "go",
    "ma", "mg", "ms", "mt", "pa", "pb", "pe", "pi", "pr",
    "rj", "rn", "ro", "rr", "rs", "sc", "se", "sp", "to",
]


@dataclass
class WFSSource:
    """Configuration for a WFS-based data source (GeoServer, TerraBrasilis, etc.)."""

    name: str
    base_url: str
    layer_template: str
    layers: list[str]
    wfs_version: str = "2.0.0"
    page_size: int = 10_000
    max_concurrent: int = 3
    epsg: int = 4674
    sort_by: str | None = None
    extra_params: dict[str, str] | None = None

    @property
    def bronze_dir(self) -> Path:
        return BRONZE_DIR / self.name.lower()

    def pagination_params(self, count: int, start: int) -> dict[str, int]:
        if self.wfs_version >= "2.0.0":
            return {"count": count, "startIndex": start}
        return {"maxFeatures": count, "startIndex": start}

    def count_param_name(self) -> str:
        return "count" if self.wfs_version >= "2.0.0" else "maxFeatures"


@dataclass
class ArcGISSource:
    """Configuration for an ArcGIS REST FeatureServer source."""

    name: str
    base_url: str
    layers: dict[str, str]
    max_record_count: int = 1000
    max_concurrent: int = 2
    epsg: int = 4674

    @property
    def bronze_dir(self) -> Path:
        return BRONZE_DIR / self.name.lower()

    @property
    def layer_ids(self) -> list[str]:
        return list(self.layers)


DataSource = WFSSource | ArcGISSource


# ---------------------------------------------------------------------------
# WFS Sources
# ---------------------------------------------------------------------------

SICAR = WFSSource(
    name="sicar",
    base_url="https://geoserver.car.gov.br/geoserver/sicar/ows",
    layer_template="sicar:sicar_imoveis_{layer}",
    layers=UF_LAYERS,
)

FUNAI = WFSSource(
    name="funai",
    base_url="https://geoserver.funai.gov.br/geoserver/Funai/ows",
    layer_template="Funai:{layer}",
    layers=["tis_poligonais"],
    sort_by="gid",
)

INCRA_QUILOMBOLAS = WFSSource(
    name="incra_quilombolas",
    base_url="https://cmr.funai.gov.br/geoserver/ows",
    layer_template="CMR-PUBLICO:{layer}",
    layers=["lim_quilombolas_a"],
    wfs_version="1.0.0",
    page_size=500,
    max_concurrent=1,
)

INCRA_SIGEF_PRIVADO = WFSSource(
    name="incra_sigef_privado",
    base_url="https://acervofundiario.incra.gov.br/i3geo/ogc.php",
    layer_template="certificada_sigef_particular_{layer}",
    layers=UF_LAYERS,
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
    extra_params={"tema": "certificada_sigef_particular_{layer}"},
)

INCRA_SIGEF_PUBLICO = WFSSource(
    name="incra_sigef_publico",
    base_url="https://acervofundiario.incra.gov.br/i3geo/ogc.php",
    layer_template="certificada_sigef_publico_{layer}",
    layers=UF_LAYERS,
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
    extra_params={"tema": "certificada_sigef_publico_{layer}"},
)

INCRA_SNCI_PRIVADO = WFSSource(
    name="incra_snci_privado",
    base_url="https://acervofundiario.incra.gov.br/i3geo/ogc.php",
    layer_template="imoveiscertificados_privado_{layer}",
    layers=UF_LAYERS,
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
    extra_params={"tema": "imoveiscertificados_privado_{layer}"},
)

INCRA_SNCI_PUBLICO = WFSSource(
    name="incra_snci_publico",
    base_url="https://acervofundiario.incra.gov.br/i3geo/ogc.php",
    layer_template="imoveiscertificados_publico_{layer}",
    layers=UF_LAYERS,
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
    extra_params={"tema": "imoveiscertificados_publico_{layer}"},
)

INCRA_ASSENTAMENTOS = WFSSource(
    name="incra_assentamentos",
    base_url="https://acervofundiario.incra.gov.br/i3geo/ogc.php",
    layer_template="assentamentos_{layer}",
    layers=UF_LAYERS,
    wfs_version="1.0.0",
    page_size=10_000,
    max_concurrent=1,
    extra_params={"tema": "assentamentos_{layer}"},
)

ICMBIO = WFSSource(
    name="icmbio",
    base_url="https://geoservicos.inde.gov.br/geoserver/ICMBio/ows",
    layer_template="ICMBio:{layer}",
    layers=["limiteucsfederais_a"],
    wfs_version="1.1.0",
    page_size=500,
    max_concurrent=1,
)

IBAMA = WFSSource(
    name="ibama",
    base_url="https://siscom.ibama.gov.br/geoserver/wfs",
    layer_template="publica:{layer}",
    layers=["vw_brasil_adm_embargo_a"],
    page_size=10_000,
    max_concurrent=1,
)

PRODES_AMAZONIA = WFSSource(
    name="prodes_amazonia",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/prodes-amazon-nb/ows",
    layer_template="prodes-amazon-nb:{layer}",
    layers=["yearly_deforestation_biome"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

PRODES_CERRADO = WFSSource(
    name="prodes_cerrado",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/prodes-cerrado-nb/ows",
    layer_template="prodes-cerrado-nb:{layer}",
    layers=["yearly_deforestation"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

PRODES_CAATINGA = WFSSource(
    name="prodes_caatinga",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/prodes-caatinga-nb/ows",
    layer_template="prodes-caatinga-nb:{layer}",
    layers=["yearly_deforestation"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

PRODES_MATA_ATLANTICA = WFSSource(
    name="prodes_mata_atlantica",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/prodes-mata-atlantica-nb/ows",
    layer_template="prodes-mata-atlantica-nb:{layer}",
    layers=["yearly_deforestation"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

PRODES_PANTANAL = WFSSource(
    name="prodes_pantanal",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/prodes-pantanal-nb/ows",
    layer_template="prodes-pantanal-nb:{layer}",
    layers=["yearly_deforestation"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

PRODES_PAMPA = WFSSource(
    name="prodes_pampa",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/prodes-pampa-nb/ows",
    layer_template="prodes-pampa-nb:{layer}",
    layers=["yearly_deforestation"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

DETER_AMAZONIA = WFSSource(
    name="deter_amazonia",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/ows",
    layer_template="deter-amz:{layer}",
    layers=["deter_amz"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

DETER_CERRADO = WFSSource(
    name="deter_cerrado",
    base_url="https://terrabrasilis.dpi.inpe.br/geoserver/deter-cerrado-nb/ows",
    layer_template="deter-cerrado-nb:{layer}",
    layers=["deter_cerrado"],
    wfs_version="1.0.0",
    page_size=50_000,
    max_concurrent=1,
)

# ---------------------------------------------------------------------------
# ArcGIS REST Sources
# ---------------------------------------------------------------------------

ANA = ArcGISSource(
    name="ana",
    base_url="https://portal1.snirh.gov.br/server/rest/services/dados_abertos",
    layers={
        "hidrografia": "Hidrografia/FeatureServer/0",
        "pivos_irrigacao": "Pivos_Mapeados/FeatureServer/0",
        "demanda_irrigacao": "Demanda_de_Irrigacao_Vazao_de_Retirada_para_Irrigacao/FeatureServer/0",
        "disponibilidade_hidrica": "Disponibilidade_Hidrica_Superficial/FeatureServer/0",
    },
    max_record_count=1000,
)

SFB = ArcGISSource(
    name="sfb",
    base_url="https://mapas.florestal.gov.br/server/rest/services",
    layers={
        "cnfp": "Hosted/CNFP_v19_03_retificado_17072025/FeatureServer/9",
        "concessoes": "Hosted/unidades_concessoes_florestais/FeatureServer/0",
        "ifn_conglomerados": "DadosAbertos-IFN/Conglomerado/FeatureServer/0",
    },
    max_record_count=2000,
)

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SOURCES: dict[str, DataSource] = {
    "sicar": SICAR,
    "funai": FUNAI,
    "incra_quilombolas": INCRA_QUILOMBOLAS,
    "incra_sigef_privado": INCRA_SIGEF_PRIVADO,
    "incra_sigef_publico": INCRA_SIGEF_PUBLICO,
    "incra_snci_privado": INCRA_SNCI_PRIVADO,
    "incra_snci_publico": INCRA_SNCI_PUBLICO,
    "incra_assentamentos": INCRA_ASSENTAMENTOS,
    "icmbio": ICMBIO,
    "ibama": IBAMA,
    "prodes_amazonia": PRODES_AMAZONIA,
    "prodes_cerrado": PRODES_CERRADO,
    "prodes_caatinga": PRODES_CAATINGA,
    "prodes_mata_atlantica": PRODES_MATA_ATLANTICA,
    "prodes_pantanal": PRODES_PANTANAL,
    "prodes_pampa": PRODES_PAMPA,
    "deter_amazonia": DETER_AMAZONIA,
    "deter_cerrado": DETER_CERRADO,
    "ana": ANA,
    "sfb": SFB,
}
