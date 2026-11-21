"""Build the June-2022 Nagaon boundary and its sub-districts from the downloaded boundary files.

  data/processed/nagaon_2022.geojson               Nagaon (Hojai excluded), datta07 Assam districts
  data/processed/nagaon_2022_geoboundaries.geojson same district from geoBoundaries 2021 (cross-check)
  data/processed/nagaon_2022_subdistricts.geojson  2011-census sub-districts inside the 2022 district

Run from the project root after src/download_data.py:  .venv\\Scripts\\python src\\prepare_boundary.py
"""
import geopandas as gpd
from pyproj import Geod

import config

RAW = config.DATA_RAW / "boundary"
OUT = config.DATA_PROCESSED
# 2011 sub-districts that went to Hojai district (2016) and are outside Nagaon in June 2022
HOJAI_SUBDISTRICTS = {"Hojai", "Doboka", "Lanka"}
geod = Geod(ellps="WGS84")


def geodesic_km2(geom) -> float:
    return abs(geod.geometry_area_perimeter(geom)[0]) / 1e6


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = gpd.read_file(RAW / "datta07" / "ASSAM_DISTRICTS.geojson").to_crs(4326)
    nag = d[d.dtname == "Nagaon"][["geometry"]].copy()
    nag["district"] = "Nagaon"
    nag["source"] = "datta07/INDIAN-SHAPEFILES ASSAM_DISTRICTS"
    nag["area_km2_geodesic"] = round(geodesic_km2(nag.geometry.iloc[0]), 2)
    nag.to_file(OUT / "nagaon_2022.geojson", driver="GeoJSON")

    gb = gpd.read_file(RAW / "geoboundaries" / "geoBoundaries-IND-ADM2.geojson")
    g = gb[gb.shapeName == "Nagaon"][["geometry"]].copy()
    g["district"] = "Nagaon"
    g["source"] = "geoBoundaries gbOpen IND ADM2 2021"
    g.to_file(OUT / "nagaon_2022_geoboundaries.geojson", driver="GeoJSON")

    s = gpd.read_file(RAW / "datta07" / "ASSAM_SUBDISTRICTS.geojson").to_crs(4326)
    s = s[(s.dtname == "Nagaon") & (~s.sdtname.isin(HOJAI_SUBDISTRICTS))].reset_index(drop=True)
    s.to_file(OUT / "nagaon_2022_subdistricts.geojson", driver="GeoJSON")

    print(f"Nagaon (datta07): {nag.area_km2_geodesic.iloc[0]} km2; geoBoundaries: {geodesic_km2(g.geometry.iloc[0]):.1f} km2")
    print("sub-districts:", ", ".join(s.sdtname), f"= {sum(geodesic_km2(x) for x in s.geometry):.1f} km2")


if __name__ == "__main__":
    main()
