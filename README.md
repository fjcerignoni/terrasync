# terrasync

Download geographic data from public GeoServer and shapefile sources.

Currently supported sources:
- **SICAR** — Cadastro Ambiental Rural (Rural Environmental Registry)
- **FUNAI** — Terras Indígenas (Indigenous Lands)
- **INCRA** — Quilombolas, Assentamentos, SIGEF e SNCI

## Requirements

- [uv](https://docs.astral.sh/uv/) installed

## Installation and usage

```bash
# Install dependencies and create virtual environment
uv sync

# Download all layers from a source
uv run terrasync --source sicar
uv run terrasync --source funai
uv run terrasync --source incra

# Download specific layers (state codes for SICAR)
uv run terrasync --source sicar --layers SP MG RJ

# Re-download layers (remove existing before downloading again)
uv run terrasync --source sicar --layers SP --reset

# Download and post-process (fix geometries, filter bounds)
uv run terrasync --source funai --process

# Enable verbose logging
uv run terrasync --source sicar --layers SP --debug
```

### CLI arguments

| Argument | Description |
|---|---|
| `--source` | **(required)** Data source to use. Available: `sicar`, `funai`, `incra` |
| `--layers ID [ID ...]` | Layer identifiers to download (default: all). E.g.: `--layers SP MG RJ` |
| `--reset` | Remove selected layers from the GPKG before downloading again |
| `--process` | Apply post-processing (filter bounds, fix geometries) and save processed layers |
| `--debug` | Enable DEBUG level logging |

Output files are saved to the `data/` directory (e.g. `data/SICAR.gpkg`, `data/Funai.gpkg`, `data/Incra.gpkg`).
Layers already downloaded are automatically skipped on reruns.

## Structure

```
src/terrasync/
├── config.py                # Source definitions and settings
├── logging_config.py        # Logging setup
├── client.py                # WFS requests with retry/backoff
├── downloader.py            # Async GeoServer download orchestration
├── shapefile_downloader.py  # Shapefile ZIP download
├── processor.py             # Geometry processing
└── main.py                  # CLI entrypoint
```
