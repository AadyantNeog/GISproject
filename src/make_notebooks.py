"""Generate the analysis notebooks from cell lists (keeps notebook diffs reviewable).

Run from the project root:  .venv\\Scripts\\python src\\make_notebooks.py
Existing notebooks are NOT overwritten unless --force is passed.
"""
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"

SETUP = """import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent / "src"))
import ee, geemap, pandas as pd
import config, ee_utils
ee_utils.init()
aoi = ee_utils.district_geometry()
print("District area (km2):", round(aoi.area(maxError=10).divide(1e6).getInfo(), 1))"""

NOTEBOOKS = {
    "01_inventory.ipynb": [
        ("md", "# 01 · Sentinel-1 scene inventory\n\nLists every Sentinel-1 IW GRD (VV+VH) acquisition over Nagaon, Jan–Jul 2022, "
               "with pass direction, relative orbit and how much of the district each scene covers. "
               "Used to pick the June event dates and a dry-season baseline from **one matching track**."),
        ("code", SETUP),
        ("code", """col = ee_utils.s1_collection(aoi, *config.INVENTORY_WINDOW)
aoi_area = aoi.area(maxError=10)

def describe(img):
    cover = img.geometry().intersection(aoi, maxError=10).area(maxError=10).divide(aoi_area).multiply(100)
    return ee.Feature(None, {
        "id": img.get("system:index"),
        "time": img.date().format("YYYY-MM-dd HH:mm"),
        "platform": img.get("platform_number"),
        "pass": img.get("orbitProperties_pass"),
        "rel_orbit": img.get("relativeOrbitNumber_start"),
        "cover_pct": cover,
    })

inv = pd.DataFrame(ee.FeatureCollection(col.map(describe)).getInfo()["features"]).pipe(
    lambda d: pd.DataFrame(list(d["properties"])))
inv["time"] = pd.to_datetime(inv["time"])
inv["date"] = inv["time"].dt.date
inv = inv.sort_values("time").reset_index(drop=True)
inv"""),
        ("md", "Scenes from the same pass can be split across two adjacent frames on the same date — group by date + track to get the district-level coverage."),
        ("code", """by_track = (inv.groupby(["pass", "rel_orbit", "date"])
              .agg(scenes=("id", "count"), cover_pct=("cover_pct", "sum"))
              .reset_index())
by_track["cover_pct"] = by_track["cover_pct"].clip(upper=100).round(1)
out = config.OUT_TABLES / "s1_inventory.csv"
out.parent.mkdir(parents=True, exist_ok=True)
inv.to_csv(out, index=False)
by_track.to_csv(config.OUT_TABLES / "s1_inventory_by_track.csv", index=False)
by_track.pivot_table(index="date", columns=["pass", "rel_orbit"], values="cover_pct")"""),
        ("code", """m = geemap.Map(center=[26.35, 92.75], zoom=9)
m.addLayer(ee.Image().paint(aoi, 0, 2), {"palette": "yellow"}, "Nagaon 2022")
june = col.filterDate(*config.EVENT_WINDOW)
m.addLayer(june.select("VH").min().clip(aoi), {"min": -28, "max": -8}, "June 2022 VH (min)")
m"""),
    ],
}


def build(force: bool) -> None:
    NB_DIR.mkdir(exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        path = NB_DIR / name
        if path.exists() and not force:
            print(f"skip  {name} (exists)")
            continue
        nb = nbf.v4.new_notebook()
        nb.metadata["kernelspec"] = {"name": "gisproject", "display_name": "Python (GISproject)", "language": "python"}
        nb.cells = [nbf.v4.new_markdown_cell(s) if k == "md" else nbf.v4.new_code_cell(s) for k, s in cells]
        nbf.write(nb, path)
        print(f"wrote {name}")


if __name__ == "__main__":
    build("--force" in sys.argv)
