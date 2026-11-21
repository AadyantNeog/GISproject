"""Clip each reference flood map to Nagaon and save as GeoPackage layers in data/processed/.

Run from the project root:  .venv\\Scripts\\python -u src\\clip_reference.py
Prints the flooded area inside the district for each product.
"""
import warnings
from pathlib import Path

import geopandas as gpd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "raw" / "reference"
OUT = ROOT / "data" / "processed" / "reference_nagaon.gpkg"
METRIC = "EPSG:32646"

nag = gpd.read_file(ROOT / "data" / "processed" / "nagaon_2022.geojson").to_crs(4326)
bbox = tuple(nag.total_bounds)

for shp in sorted(REF.glob("*/*.shp")):
    name = shp.parent.name
    gdf = gpd.read_file(shp, bbox=bbox)
    if gdf.empty:
        print(f"{name:24s} no features in district bbox")
        continue
    gdf = gdf.to_crs(4326)
    # Some products (MBRSC) are one giant multipolygon: split into parts and keep only
    # parts touching the district bbox before the (expensive) validity repair.
    gdf = gdf.explode(index_parts=False, ignore_index=True)
    gdf = gdf[gdf.intersects(nag.envelope.iloc[0])]
    gdf["geometry"] = gdf.geometry.make_valid()
    clipped = gpd.clip(gdf, nag)
    clipped = clipped[clipped.geometry.area > 0]
    if clipped.empty:
        print(f"{name:24s} 0 km2 inside Nagaon")
        continue
    dissolved = clipped.dissolve().to_crs(METRIC)
    km2 = dissolved.geometry.area.sum() / 1e6
    dissolved.to_crs(4326).to_file(OUT, layer=name, driver="GPKG")
    print(f"{name:24s} {km2:8.1f} km2 inside Nagaon  ({len(clipped)} polygons; fields: {list(gdf.columns[:5])})")
