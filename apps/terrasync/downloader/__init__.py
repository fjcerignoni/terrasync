"""Bronze layer ingestion: WFS (JSON + GML), ArcGIS REST, ZIP shapefile.

Public API:
    download_all(source, layers=None, reset=False)
    download_layer(source, layer_id, reset=False)
"""

from .orchestrator import download_all, download_layer

__all__ = ["download_all", "download_layer"]
