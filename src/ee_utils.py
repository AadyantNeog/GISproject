"""Earth Engine helpers shared by the notebooks."""
from __future__ import annotations

import json

import ee

from config import BOUNDARY_FILE, EE_PROJECT


def init() -> None:
    """Initialise Earth Engine with the project in config.py (run `earthengine authenticate` once first)."""
    if EE_PROJECT.startswith("YOUR-"):
        raise RuntimeError("Set EE_PROJECT in src/config.py to your Google Cloud project ID.")
    ee.Initialize(project=EE_PROJECT)


def district_geometry() -> ee.Geometry:
    """Nagaon (June 2022 extent) as an ee.Geometry, read from the local GeoJSON."""
    gj = json.loads(BOUNDARY_FILE.read_text())
    geoms = [f["geometry"] for f in gj["features"]]
    return ee.FeatureCollection([ee.Feature(ee.Geometry(g)) for g in geoms]).geometry().dissolve()


def s1_collection(aoi: ee.Geometry, start: str, end: str) -> ee.ImageCollection:
    """Sentinel-1 IW GRD scenes with both VV and VH over the AOI."""
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    )
