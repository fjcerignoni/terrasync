# terrasync

Acquire, store and process Brazilian geographic data focused on land tenure and the Forest Code.

Data is downloaded to **bronze** (raw Parquet), cleaned via **dbt** into **silver**, and catalogued in a DuckDB database.

## Sources

### WFS (18 sources)

| Source | Endpoint | Data |
|--------|----------|------|
| **SICAR** | geoserver.car.gov.br | Cadastro Ambiental Rural — 27 layers (one per state) |
| **FUNAI** | geoserver.funai.gov.br | Terras Indígenas (polygons) |
| **INCRA** (6 sources) | acervofundiario.incra.gov.br | Quilombolas, Assentamentos, SIGEF, SNCI (public/private) |
| **ICMBio** | geoservicos.inde.gov.br | Unidades de Conservação federais |
| **IBAMA** | siscom.ibama.gov.br | Embargos ambientais |
| **PRODES** (6 biomes) | terrabrasilis.dpi.inpe.br | Desmatamento anual (Amazônia, Cerrado, Caatinga, Mata Atlântica, Pantanal, Pampa) |
| **DETER** (2 biomes) | terrabrasilis.dpi.inpe.br | Alertas de desmatamento (Amazônia, Cerrado) |

### ArcGIS REST (2 sources)

| Source | Endpoint | Data |
|--------|----------|------|
| **ANA** | portal1.snirh.gov.br | Hidrografia, pivôs de irrigação, demanda e disponibilidade hídrica |
| **SFB** | mapas.florestal.gov.br | Cadastro Nacional de Florestas Públicas, concessões florestais, IFN |

## Requirements

- [uv](https://docs.astral.sh/uv/) installed

## Installation and usage

```bash
uv sync
```

### Ingest (bronze)

```bash
# Download all layers from a source
uv run terrasync ingest --source sicar
uv run terrasync ingest --source funai
uv run terrasync ingest --source prodes_amazonia
uv run terrasync ingest --source ana

# Download by group (downloads all sub-sources)
uv run terrasync ingest --source incra     # quilombolas + sigef + snci + assentamentos
uv run terrasync ingest --source prodes    # all 6 biomes
uv run terrasync ingest --source deter     # amazonia + cerrado

# Download everything
uv run terrasync ingest --source all

# Download specific layers (WFS sources with multiple layers)
uv run terrasync ingest --source sicar --layers sp mg rj
uv run terrasync ingest --source incra_sigef_privado --layers sp pr

# Re-download (remove existing before downloading)
uv run terrasync ingest --source sicar --layers sp --reset

# Verbose logging
uv run terrasync ingest --source funai --debug
```

### Transform (silver)

```bash
# Run all dbt silver models
uv run terrasync transform

# Run a specific model
uv run terrasync transform --select slv_funai

# Full refresh
uv run terrasync transform --full-refresh
```

### Catalog (DuckDB views)

`ingest` already refreshes the DuckDB catalog at the end of every run. Use this when bronze parquets were added/removed/moved outside the CLI and you need to resync the views:

```bash
uv run terrasync catalog
```

This rescans `data/bronze/*/` and recreates the `bronze_{source}_{layer}` views in `data/terrasync.duckdb`.

You can also run dbt directly from the dbt project directory:

```bash
cd apps/dbt
uv run dbt deps
uv run dbt run
uv run dbt run -s slv_funai
```

### Postgres (infra)

The PostGIS container (used by future silver/gold layers) lives under `infra/`:

```bash
cd infra
docker compose up -d postgres
docker compose down
```

The compose file bind-mounts `../data/silver` read-only at `/data/silver` inside the container so PostGIS can read silver parquets via `pg_parquet`.

## Data layout

```
data/
├── bronze/                          # Raw data (Parquet per layer)
│   ├── sicar/*.parquet              # one file per UF
│   ├── funai/*.parquet
│   ├── incra_quilombolas/*.parquet
│   ├── incra_assentamentos/*.parquet
│   ├── incra_sigef_privado/*.parquet
│   ├── ...
│   ├── icmbio/*.parquet
│   ├── ibama/*.parquet
│   ├── prodes_amazonia/*.parquet
│   ├── ...
│   ├── deter_amazonia/*.parquet
│   ├── ana/*.parquet                # one file per layer
│   └── sfb/*.parquet
├── silver/                          # Cleaned data (dbt silver models, EPSG:4326)
│   ├── slv_sicar.parquet
│   ├── slv_funai.parquet
│   ├── slv_incra_*.parquet
│   ├── slv_prodes.parquet
│   ├── slv_deter.parquet
│   └── ...
├── exports/<client>/                # Per-client extracts (versioned v=YYYY-MM-DD)
├── cache/                           # Transient artifacts (ZIP downloads)
│   └── *.zip                        # auto-removed after parquet success
└── terrasync.duckdb                 # Catalogue with views over parquet files
```

### ZIP source caching

Sources of type `zip_shapefile` keep the downloaded archive at `data/cache/{source}.zip` until the parquet conversion succeeds, then delete it. If the conversion fails, the cached ZIP stays on disk so the next run skips the download. `--reset` clears both the parquet and the cached ZIP.

## Project structure

```
├── pyproject.toml
├── uv.lock
├── apps/
│   ├── terrasync/           # Python ingestion engine + CLI
│   │   ├── sources.yaml     # Declarative source catalog
│   │   ├── config.py        # Pydantic models + YAML loader
│   │   ├── paths.py         # repo_root() + DATA_DIR + DBT_DIR (cwd-independent)
│   │   ├── downloader/      # WFS (JSON/GML) + ArcGIS REST + ZIP shapefile strategies
│   │   ├── catalog.py       # DuckDB catalogue refresh
│   │   ├── manifest.py      # Acquisition log (parquet footer + runs.jsonl)
│   │   ├── logging_config.py
│   │   └── main.py          # CLI entrypoint (ingest / transform / catalog)
│   ├── dbt/                 # dbt project (run `dbt` from here)
│   │   ├── dbt_project.yml
│   │   ├── profiles.yml
│   │   ├── packages.yml
│   │   ├── macros/          # clean_geometry, area_ha, bronze_path, silver_path, export_path
│   │   └── models/
│   │       ├── silver/      # 11 dbt silver models (bronze → silver, DuckDB)
│   │       └── exports/     # per-client extracts (e.g. scw/sicar_opi)
│   ├── api/                 # placeholder (future HTTP API)
│   └── web/                 # placeholder (future frontend)
├── infra/
│   ├── docker-compose.yml   # run `docker compose` from here
│   └── docker/postgres/     # PostGIS + pg_parquet image
└── data/                    # shared, gitignored
```

The CLI (`uv run terrasync ...`) works from any cwd: `apps/terrasync/paths.py:repo_root()` walks up to `pyproject.toml` and resolves `data/` and `apps/dbt/` absolutely.

## Source groups

Sources can be ingested individually or by group:

| Group | Sources |
|-------|--------|
| `incra` | quilombolas, sigef_privado, sigef_publico, snci_privado, snci_publico, assentamentos |
| `prodes` | amazonia, cerrado, caatinga, mata_atlantica, pantanal, pampa |
| `deter` | amazonia, cerrado |
| `ana` | hidrografia, pivos, demanda, disponibilidade |
| `sfb` | cnfp, concessoes, ifn_conglomerados |
