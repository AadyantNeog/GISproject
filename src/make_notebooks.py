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
    "02_flood_detection.ipynb": [
        ("md", "# 02 · Flood detection, June 2022\n\n"
               "Inputs: stacks from `src/fetch_stacks.py` (Lee-filtered VV/VH for each date + dry-season "
               "baseline from the same track; HAND, slope, JRC, WorldCover), all on one 10 m UTM 46N grid.\n\n"
               "Rule (defaults in `config.DEFAULT_PARAMS`): VH drop vs. baseline < −3 dB **and** VH below an "
               "automatic edge-based Otsu threshold, excluding HAND ≥ 15 m, slope ≥ 5°, JRC permanent water "
               "(≥ 10 months), and patches < 8 pixels. Classes: 0 dry, 1 flood, 2 permanent water, 255 no data."),
        ("code", """import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent / "src"))
import numpy as np, pandas as pd, geopandas as gpd, matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
import config, classify as C

st = C.static()
print("district area on grid:", round(st["district"].sum() * C.PIX_KM2, 1), "km2")"""),
        ("md", "## Classify every date"),
        ("code", """rows, maps = [], {}
for date, orb in config.EVENT_DATES:
    s1 = C.load_s1(date, orb)
    cl, info = C.classify(s1, st=st)
    C.write_classes(cl, config.OUT_RASTERS / f"flood_{date.replace('-', '')}_t{orb}.tif")
    maps[(date, orb)] = cl
    rows.append({"date": date, "track": orb, "pass": config.TRACKS[orb], **C.areas_km2(cl),
                 "vh_threshold_db": round(info["vh_threshold"], 2), "vh_otsu_db": round(info.get("vh_otsu", np.nan), 2)})
    del s1

# footprint observed on all six dates -> fair comparison between tracks
common = np.logical_and.reduce([m != 255 for m in maps.values()])
for r, cl in zip(rows, maps.values()):
    r["flood_common_km2"] = C.areas_km2(cl, common)["flood_km2"]
areas = pd.DataFrame(rows).round(1)
areas.to_csv(config.OUT_TABLES / "flood_area_by_date.csv", index=False)
print("common footprint:", round(common.sum() * C.PIX_KM2, 1), "km2")
areas"""),
        ("md", "## Flooded area by sub-district (2011 census sub-districts inside 2022 Nagaon)"),
        ("code", """subs = gpd.read_file(config.DATA_PROCESSED / "nagaon_2022_subdistricts.geojson").reset_index(drop=True)
sub_id = C.rasterize_gdf(subs, values=range(1, len(subs) + 1))
n = len(subs) + 1
recs = []
for (date, orb), cl in maps.items():
    flood = np.bincount(sub_id[cl == 1], minlength=n) * C.PIX_KM2
    obs = np.bincount(sub_id[cl != 255], minlength=n) * C.PIX_KM2
    for i, name in enumerate(subs["sdtname"], start=1):
        recs.append({"date": date, "track": orb, "subdistrict": name,
                     "flood_km2": flood[i], "observed_km2": obs[i],
                     "flood_pct_of_observed": 100 * flood[i] / obs[i] if obs[i] else np.nan})
by_sub = pd.DataFrame(recs).round(1)
by_sub.to_csv(config.OUT_TABLES / "flood_area_by_subdistrict.csv", index=False)
by_sub.pivot(index="subdistrict", columns="date", values="flood_km2")"""),
        ("md", "## Maps"),
        ("code", """cmap = ListedColormap(["#e9e6df", "#1f78d1", "#0b2e59", "#ffffff"])
norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 255.5], cmap.N)
district = gpd.read_file(config.BOUNDARY_FILE).to_crs(config.CRS_METRIC)
p = C.profile(); t = p["transform"]
extent = [t.c, t.c + t.a * p["width"], t.f + t.e * p["height"], t.f]

fig, axes = plt.subplots(2, 3, figsize=(15, 9.5), constrained_layout=True)
for ax, ((date, orb), cl), r in zip(axes.T.ravel(), maps.items(), rows):
    ax.imshow(cl[::4, ::4], cmap=cmap, norm=norm, extent=extent, interpolation="nearest")
    district.boundary.plot(ax=ax, color="k", lw=0.6)
    ax.set_title(f"{date}  track {orb} ({config.TRACKS[orb][:4].lower()})\\nflood {r['flood_km2']:.0f} km²", fontsize=10)
    ax.set_axis_off()
fig.suptitle("Sentinel-1 flood extent, Nagaon, June 2022 (blue = flood, navy = permanent water, white = not observed)")
fig.savefig(config.OUT_FIGURES / "flood_maps_june2022.png", dpi=150)
plt.show()"""),
        ("code", """fig, ax = plt.subplots(figsize=(8, 4))
for orb, mk in [(77, "o"), (41, "s")]:
    d = areas[areas.track == orb]
    ax.plot(pd.to_datetime(d.date), d.flood_common_km2, mk + "-", label=f"track {orb} ({config.TRACKS[orb].lower()})")
ax.set_ylabel("flooded area in common footprint (km²)"); ax.legend(); ax.grid(alpha=.3)
ax.set_title("Flood extent through June 2022")
fig.autofmt_xdate(); fig.savefig(config.OUT_FIGURES / "flood_area_timeseries.png", dpi=150, bbox_inches="tight")
plt.show()"""),
        ("md", "## Quick check against independent reference maps\n\n"
               "Full validation is in notebook 06; this is a sanity check. Metrics are computed on pixels inside "
               "the district observed on our date, treating permanent water as not flooded."),
        ("code", """REF = config.DATA_PROCESSED / "reference_nagaon.gpkg"
pairs = [("mbrsc_s1_20220616", ("2022-06-16", 41)),
         ("eosrs_alos2_20220622", ("2022-06-18", 77)),
         ("eosrs_alos2_20220622", ("2022-06-28", 41))]
out = []
for layer, key in pairs:
    ref = C.rasterize_gdf(gpd.read_file(REF, layer=layer)).astype(bool)
    cl = maps[key]; ok = cl != 255
    ours = (cl == 1) & ok; refm = ref & ok
    tp = np.count_nonzero(ours & refm); fp = np.count_nonzero(ours & ~refm); fn = np.count_nonzero(~ours & refm)
    out.append({"reference": layer, "our_date": key[0], "track": key[1],
                "ref_km2": refm.sum() * C.PIX_KM2, "ours_km2": ours.sum() * C.PIX_KM2,
                "precision": tp / (tp + fp), "recall": tp / (tp + fn),
                "f1": 2 * tp / (2 * tp + fp + fn), "iou": tp / (tp + fp + fn)})
check = pd.DataFrame(out).round(3)
check.to_csv(config.OUT_TABLES / "reference_quickcheck.csv", index=False)
check"""),
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
