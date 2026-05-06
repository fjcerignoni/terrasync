import argparse
import asyncio
import logging

from .catalog import refresh_catalog
from .config import SOURCES, ArcGISSource, WFSSource
from .downloader import download_all
from .logging_config import setup_logging


def _add_ingest_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("ingest", help="Download data to bronze layer.")
    p.add_argument(
        "--source",
        choices=list(SOURCES),
        required=True,
        help="Data source to use. Available: " + ", ".join(SOURCES),
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
    return parser.parse_args()


def _run_ingest(args: argparse.Namespace, logger: logging.Logger) -> None:
    source = SOURCES[args.source]

    if isinstance(source, WFSSource):
        valid_layers = source.layers
    elif isinstance(source, ArcGISSource):
        valid_layers = source.layer_ids

    layers = [lid.lower() for lid in args.layers] if args.layers else valid_layers

    invalid = [lid for lid in layers if lid not in valid_layers]
    if invalid:
        logger.error("Invalid layers: %s", invalid)
        raise SystemExit(1)

    logger.info("Starting ingest for %s: %s", args.source, layers)
    asyncio.run(download_all(source, layers, reset=args.reset))
    logger.info("All downloads finished.")

    logger.info("Refreshing DuckDB catalog...")
    refresh_catalog()


def _run_transform(args: argparse.Namespace, logger: logging.Logger) -> None:
    from .config import SILVER_DIR
    from dbt.cli.main import dbtRunner

    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    dbt_args = ["run"]
    if args.full_refresh:
        dbt_args.append("--full-refresh")
    if args.select:
        dbt_args.extend(["--select", args.select])
    dbt_args.extend(["--profiles-dir", "."])
    dbt_args.extend(["--project-dir", "."])

    logger.info("Running: dbt %s", " ".join(dbt_args))
    res = dbtRunner().invoke(dbt_args)
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


if __name__ == "__main__":
    run()
