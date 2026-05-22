import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from .catalog import refresh_catalog
from .config import SOURCES, SOURCE_GROUPS, resolve_sources
from .downloader import download_all
from .logging_config import setup_logging
from .paths import DBT_DIR, DBT_TARGET, repo_root


def _load_dotenv() -> None:
    """Carrega .env da raiz do repo sem depender de python-dotenv."""
    env_file = repo_root() / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

_VALID_SOURCE_CHOICES = sorted(set(list(SOURCES) + list(SOURCE_GROUPS) + ["all"]))


def _add_ingest_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("ingest", help="Download data to bronze layer.")
    p.add_argument(
        "--source",
        choices=_VALID_SOURCE_CHOICES,
        required=True,
        help="Data source, group, or 'all'. Groups: " + ", ".join(SOURCE_GROUPS),
    )
    p.add_argument(
        "--layers",
        nargs="+",
        metavar="ID",
        default=None,
        help="Layer identifiers to download (default: all).",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Remove selected layers before downloading again.",
    )


def _add_transform_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("transform", help="Run dbt models (bronze -> silver).")
    p.add_argument(
        "--full-refresh",
        action="store_true",
        help="Full refresh all models.",
    )
    p.add_argument(
        "--select",
        metavar="SELECTOR",
        default=None,
        help="dbt node selector (e.g. staging.stg_sicar).",
    )


def _add_catalog_parser(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser(
        "catalog",
        help="Refresh DuckDB catalog views over bronze parquet files.",
    )


def _add_status_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "status",
        help="Launch the Streamlit observability dashboard (requires extra 'dashboard').",
    )
    p.add_argument("--port", type=int, default=8501, help="Port for the Streamlit server.")
    p.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window automatically.",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="terrasync — acquire, store and process Brazilian geographic data."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG level logging.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_ingest_parser(subparsers)
    _add_transform_parser(subparsers)
    _add_catalog_parser(subparsers)
    _add_status_parser(subparsers)
    return parser.parse_args()


def _run_ingest(args: argparse.Namespace, logger: logging.Logger) -> None:
    targets = resolve_sources(args.source)
    requested = [lid.lower() for lid in args.layers] if args.layers else None

    # When targeting a group, --layers may refer to sub-source names
    # (e.g. --source incra --layers incra_sigef_privado) rather than
    # layer IDs within a source (e.g. --source sicar --layers sp).
    if args.source in SOURCE_GROUPS and requested:
        source_names = {s.name for s in targets}
        if all(r in source_names for r in requested):
            targets = [s for s in targets if s.name in requested]
            requested = None  # download all layers within each matched source

    async def _ingest_one(source):
        valid_layers = source.layer_ids
        layers = requested if requested is not None else valid_layers
        invalid = [lid for lid in layers if lid not in valid_layers]
        if invalid:
            logger.error("[%s] Invalid layers: %s", source.name, invalid)
            return

        logger.info("Starting ingest for %s: %d layers", source.name, len(layers))
        await download_all(source, layers, reset=args.reset)
        logger.info("[%s] All downloads finished.", source.name)

    async def _run_all():
        results = await asyncio.gather(
            *[_ingest_one(source) for source in targets],
            return_exceptions=True,
        )
        failed = []
        for source, result in zip(targets, results):
            if isinstance(result, BaseException):
                logger.error("[%s] Ingest failed: %s", source.name, result, exc_info=result)
                failed.append(source.name)
        if failed:
            logger.error("Failed sources: %s", failed)

    asyncio.run(_run_all())

    logger.info("Refreshing DuckDB catalog...")
    refresh_catalog()


def _ensure_external_dirs(
    runner, logger: logging.Logger, vars_override: str | None = None, select: str | None = None
) -> None:
    """Pre-create parent dirs for `materialized=external` models that will actually run.

    DuckDB's COPY TO does not create nested parent directories. For locations
    like `data/exports/<client>/<model>/v=<date>/...`, the run fails with an
    IO Error if the dir doesn't already exist. We resolve which models will run
    via `dbt ls` (respecting --select), then mkdir only those.
    """
    import json
    from pathlib import Path

    dbt_dir = str(DBT_DIR)
    parse_cmd = ["parse", "--profiles-dir", dbt_dir, "--project-dir", dbt_dir]
    if vars_override:
        parse_cmd.extend(["--vars", vars_override])
    parse_res = runner.invoke(parse_cmd)
    if not parse_res.success:
        return  # let `dbt run` surface the same parse error

    manifest_path = DBT_TARGET / "manifest.json"
    if not manifest_path.exists():
        return

    # Resolve which models will actually run using `dbt ls`.
    ls_cmd = ["ls", "--profiles-dir", dbt_dir, "--project-dir", dbt_dir, "--resource-type", "model"]
    if vars_override:
        ls_cmd.extend(["--vars", vars_override])
    if select:
        ls_cmd.extend(["--select", select])
    ls_res = runner.invoke(ls_cmd)
    if not ls_res.success:
        return

    # `dbt ls` outputs "project.model_name" per line; extract the model names.
    selected_names: set[str] = set()
    for line in (ls_res.result or []):
        line = str(line).strip()
        if "." in line:
            selected_names.add(line.split(".")[-1])
        elif line:
            selected_names.add(line)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "model":
            continue
        if node.get("name") not in selected_names:
            continue
        cfg = node.get("config", {}) or {}
        if cfg.get("materialized") != "external":
            continue
        location = cfg.get("location")
        if not location:
            continue
        loc_path = Path(location)
        if not loc_path.is_absolute():
            loc_path = (DBT_DIR / loc_path).resolve()
        parent = loc_path.parent
        if parent and not parent.exists():
            logger.info("Pre-creating output dir for %s: %s", node.get("name"), parent)
            parent.mkdir(parents=True, exist_ok=True)


def _run_transform(args: argparse.Namespace, logger: logging.Logger) -> None:
    import json
    import os

    from dbt.cli.main import dbtRunner
    from .config import DATA_DIR, DUCKDB_PATH

    # Injeta paths absolutas — dbtRunner resolve paths relativas contra o cwd do
    # processo (não contra --project-dir), então não podemos depender de relativos.
    os.environ["TERRASYNC_DUCKDB_PATH"] = str(DUCKDB_PATH)
    os.environ["TERRASYNC_DATA_ROOT"] = DATA_DIR.as_posix()
    vars_override = json.dumps({"data_root": DATA_DIR.as_posix()})

    runner = dbtRunner()
    _ensure_external_dirs(runner, logger, vars_override, select=args.select)

    dbt_args = ["run"]
    if args.full_refresh:
        dbt_args.append("--full-refresh")
    if args.select:
        dbt_args.extend(["--select", args.select])
    dbt_dir = str(DBT_DIR)
    dbt_args.extend(["--profiles-dir", dbt_dir])
    dbt_args.extend(["--project-dir", dbt_dir])
    dbt_args.extend(["--vars", vars_override])

    logger.info("Running: dbt %s", " ".join(dbt_args))
    res = runner.invoke(dbt_args)
    if not res.success:
        logger.error("dbt run failed.")
        raise SystemExit(1)
    logger.info("Transform finished.")


def _run_status(args: argparse.Namespace, logger: logging.Logger) -> None:
    try:
        from streamlit.web import cli as stcli
    except ImportError:
        logger.error(
            "streamlit não instalado. Rode: uv sync --extra dashboard"
        )
        raise SystemExit(1)

    app_path = Path(__file__).parent / "dashboard" / "app.py"
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--browser.gatherUsageStats=false",
        f"--server.port={args.port}",
    ]
    if args.no_browser:
        sys.argv.append("--server.headless=true")
    logger.info("Launching dashboard at http://localhost:%d", args.port)
    sys.exit(stcli.main())


def run() -> None:
    _load_dotenv()
    args = _parse_args()
    logger = setup_logging()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.command == "ingest":
        _run_ingest(args, logger)
    elif args.command == "transform":
        _run_transform(args, logger)
    elif args.command == "catalog":
        logger.info("Refreshing DuckDB catalog...")
        refresh_catalog()
    elif args.command == "status":
        _run_status(args, logger)


if __name__ == "__main__":
    run()
