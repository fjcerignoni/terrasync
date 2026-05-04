import argparse
import asyncio
import logging

from .config import SOURCES, GeoServerSource, ShapefileSource
from .downloader import download_all as geoserver_download_all
from .logging_config import setup_logging
from .processor import process_all
from .shapefile_downloader import download_all as shapefile_download_all


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download geographic data from public GeoServer sources."
    )
    parser.add_argument(
        "--source",
        choices=list(SOURCES),
        required=True,
        help="Data source to use. Available: " + ", ".join(SOURCES),
    )
    parser.add_argument(
        "--layers",
        nargs="+",
        metavar="ID",
        default=None,
        help="Layer identifiers to download (default: all). E.g.: --layers SP MG RJ",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove selected layers before downloading again.",
    )
    parser.add_argument(
        "--process",
        action="store_true",
        help="Apply post-processing (filter bounds, fix geometries) and save processed layers.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG level logging.",
    )
    return parser.parse_args()


def run() -> None:
    args = _parse_args()
    logger = setup_logging()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    source = SOURCES[args.source]
    layers = [lid.lower() for lid in args.layers] if args.layers else source.layers

    invalid = [lid for lid in layers if lid not in source.layers]
    if invalid:
        logger.error("Invalid layers: %s", invalid)
        raise SystemExit(1)

    logger.info("Starting download for: %s", layers)
    if isinstance(source, GeoServerSource):
        asyncio.run(geoserver_download_all(source, layers, reset=args.reset))
    elif isinstance(source, ShapefileSource):
        shapefile_download_all(source, layers, reset=args.reset)
    logger.info("All downloads finished.")

    if args.process:
        logger.info("Starting processing for: %s", layers)
        process_all(source, layers)
        logger.info("Processing finished.")


if __name__ == "__main__":
    run()
