import argparse
import asyncio
import logging

from .catalog import refresh_catalog
from .config import SOURCES, SOURCE_GROUPS, resolve_sources
from .downloader import download_all
from .logging_config import setup_logging

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
        failed = []
        for source in targets:
            try:
                await _ingest_one(source)
            except Exception:
                logger.exception("[%s] Ingest failed, continuing...", source.name)
                failed.append(source.name)
        if failed:
            logger.error("Failed sources: %s", failed)

    asyncio.run(_run_all())

    logger.info("Refreshing DuckDB catalog...")
    refresh_catalog()


def _ensure_external_dirs(runner, logger: logging.Logger) -> None:
    """Pre-create parent dirs for every `materialized=external` model.

    DuckDB's COPY TO does not create nested parent directories. For locations
    like `data/exports/<client>/<model>/v=<date>/...`, the run fails with an
    IO Error if the dir doesn't already exist. We parse the project first,
    walk the manifest, and `mkdir -p` each external model's parent.
    """
    import json
    from pathlib import Path

    parse_res = runner.invoke(["parse", "--profiles-dir", ".", "--project-dir", "."])
    if not parse_res.success:
        return  # let `dbt run` surface the same parse error

    manifest_path = Path("target") / "manifest.json"
    if not manifest_path.exists():
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "model":
            continue
        cfg = node.get("config", {}) or {}
        if cfg.get("materialized") != "external":
            continue
        location = cfg.get("location")
        if not location:
            continue
        parent = Path(location).parent
        if parent and not parent.exists():
            logger.info("Pre-creating output dir for %s: %s", node.get("name"), parent)
            parent.mkdir(parents=True, exist_ok=True)


def _run_transform(args: argparse.Namespace, logger: logging.Logger) -> None:
    from dbt.cli.main import dbtRunner

    runner = dbtRunner()
    _ensure_external_dirs(runner, logger)

    dbt_args = ["run"]
    if args.full_refresh:
        dbt_args.append("--full-refresh")
    if args.select:
        dbt_args.extend(["--select", args.select])
    dbt_args.extend(["--profiles-dir", "."])
    dbt_args.extend(["--project-dir", "."])

    logger.info("Running: dbt %s", " ".join(dbt_args))
    res = runner.invoke(dbt_args)
    if not res.success:
        logger.error("dbt run failed.")
        raise SystemExit(1)
    logger.info("Transform finished.")


def run() -> None:
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


if __name__ == "__main__":
    run()
