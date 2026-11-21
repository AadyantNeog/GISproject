"""Generate the analysis notebooks from cell lists (keeps notebook diffs reviewable).

Run from the project root:  .venv\\Scripts\\python src\\make_notebooks.py
Existing notebooks are NOT overwritten unless --force is passed; give prefixes (e.g. 03) to limit.
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
    "03_exposure.ipynb": [
        ("md", "# 03 · Settlement exposure\n\n"
               "Built-up land = ESA WorldCover 2021 class 50 (10 m). **Direct overlap is close to zero by "
               "construction**: SAR cannot detect water among buildings (double-bounce keeps built-up pixels "
               "bright), so the flood mask almost never falls on built-up pixels. Exposure is therefore measured "
               "as built-up land **within a distance of mapped flood water** — 50 m (main), with 30 m and 100 m "
               "as sensitivity. This indicates spatial proximity to inundation, not confirmed damage or "
               "affected population."),
        ("code", """import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent / "src"))
import numpy as np, pandas as pd, geopandas as gpd, rasterio, matplotlib.pyplot as plt
from scipy import ndimage
from shapely.geometry import box
import config, classify as C

st = C.static()
district = st["district"]
built = (st["worldcover"] == 50) & district
DISTANCES_M = [0, 30, 50, 100]
MAIN_M = 50
print("built-up in district:", round(built.sum() * C.PIX_KM2, 1), "km2",
      f"({100 * built.sum() / district.sum():.1f} % of district)")

maps = {}
for date, orb in config.EVENT_DATES:
    with rasterio.open(config.OUT_RASTERS / f"flood_{date.replace('-', '')}_t{orb}.tif") as r:
        maps[(date, orb)] = r.read(1)"""),
        ("md", "## Flood frequency and union of all dates\n\n"
               "`any_flood` = flooded on at least one June date. `freq` = number of dates flooded."),
        ("code", """freq = np.zeros(district.shape, np.uint8)
obs = np.zeros(district.shape, np.uint8)
for cl in maps.values():
    freq += (cl == 1); obs += (cl != 255)
any_flood = freq > 0
p = C.profile() | {"count": 2, "dtype": "uint8", "nodata": 255, "compress": "deflate"}
with rasterio.open(config.OUT_RASTERS / "flood_frequency_june2022.tif", "w", **p) as dst:
    dst.write(np.where(district, freq, 255), 1); dst.write(np.where(district, obs, 255), 2)
    dst.descriptions = ("dates_flooded", "dates_observed")
print("flooded on >=1 date:", round(any_flood.sum() * C.PIX_KM2, 1), "km2;",
      "on >=3 dates:", round((freq >= 3).sum() * C.PIX_KM2, 1), "km2")"""),
        ("md", "## Exposure by date"),
        ("code", """def dist_to_flood_m(flood):
    \"\"\"Euclidean distance (m) from every pixel to the nearest flood pixel.\"\"\"
    return (ndimage.distance_transform_edt(~flood) * 10).astype(np.float32)

# settlement clusters = 8-connected patches of built-up pixels
clusters, n_clusters = ndimage.label(built, structure=np.ones((3, 3), bool))
print("built-up clusters in district:", n_clusters)

def exposure_row(flood, observed, label):
    d = dist_to_flood_m(flood)
    b_obs = built & observed
    row = {"scenario": label, "built_observed_km2": b_obs.sum() * C.PIX_KM2}
    for m in DISTANCES_M:
        e = b_obs & (d <= m) if m else b_obs & flood
        row[f"exposed_{m}m_km2"] = e.sum() * C.PIX_KM2
        row[f"exposed_{m}m_pct"] = 100 * e.sum() / max(b_obs.sum(), 1)
    hit = np.unique(clusters[b_obs & (d <= MAIN_M)]); hit = hit[hit > 0]
    row[f"clusters_within_{MAIN_M}m"] = len(hit)
    return row, d

rows, dist = [], {}
for (date, orb), cl in maps.items():
    r, d = exposure_row(cl == 1, cl != 255, f"{date} t{orb}")
    rows.append(r); dist[(date, orb)] = d
r, d_any = exposure_row(any_flood, obs > 0, "any June date")
rows.append(r)
expo = pd.DataFrame(rows).round(2)
expo.to_csv(config.OUT_TABLES / "exposure_by_date.csv", index=False)
expo"""),
        ("md", "## Exposure by sub-district (main 50 m distance)"),
        ("code", """subs = gpd.read_file(config.DATA_PROCESSED / "nagaon_2022_subdistricts.geojson").reset_index(drop=True)
sub_id = C.rasterize_gdf(subs, values=range(1, len(subs) + 1))
n = len(subs) + 1
recs = []
scen = list(dist.items()) + [(("any", "June"), d_any)]
for (date, orb), d in scen:
    observed = (maps[(date, orb)] != 255) if date != "any" else (obs > 0)
    b_obs = built & observed
    tot = np.bincount(sub_id[b_obs], minlength=n) * C.PIX_KM2
    exp = np.bincount(sub_id[b_obs & (d <= MAIN_M)], minlength=n) * C.PIX_KM2
    for i, name in enumerate(subs["sdtname"], start=1):
        recs.append({"scenario": f"{date} t{orb}" if date != "any" else "any June date",
                     "subdistrict": name, "built_km2": tot[i], "exposed_km2": exp[i],
                     "exposed_pct": 100 * exp[i] / tot[i] if tot[i] else np.nan})
by_sub = pd.DataFrame(recs).round(2)
by_sub.to_csv(config.OUT_TABLES / "exposure_by_subdistrict.csv", index=False)
by_sub.pivot(index="subdistrict", columns="scenario", values="exposed_km2")"""),
        ("code", """by_sub[by_sub.scenario == "any June date"].sort_values("exposed_km2", ascending=False)"""),
        ("md", "## 1 km grid summary (for mapping where exposure concentrates)"),
        ("code", """prof = C.profile(); t = prof["transform"]; H, W = prof["height"], prof["width"]
k = 100  # 100 x 10 m = 1 km cells
Hc, Wc = H // k, W // k
def block_sum(a):
    return a[:Hc * k, :Wc * k].reshape(Hc, k, Wc, k).sum(axis=(1, 3)) * C.PIX_KM2

exp_any = block_sum(built & (obs > 0) & (d_any <= MAIN_M))
built_c = block_sum(built)
peak = ("2022-06-30", 77)
exp_peak = block_sum(built & (maps[peak] != 255) & (dist[peak] <= MAIN_M))
flood_any_c = block_sum(any_flood)
cells = []
for i in range(Hc):
    for j in range(Wc):
        x0 = t.c + j * k * t.a; y1 = t.f + i * k * t.e
        cells.append(box(x0, y1 + k * t.e, x0 + k * t.a, y1))
grid = gpd.GeoDataFrame({"built_km2": built_c.ravel(), "exposed_any_km2": exp_any.ravel(),
                         "exposed_30jun_km2": exp_peak.ravel(), "flood_any_km2": flood_any_c.ravel()},
                        geometry=cells, crs=prof["crs"])
dist_poly = gpd.read_file(config.BOUNDARY_FILE).to_crs(prof["crs"])
grid = grid[grid.intersects(dist_poly.geometry.iloc[0])].reset_index(drop=True)
grid["exposed_any_pct"] = np.where(grid.built_km2 > 0, 100 * grid.exposed_any_km2 / grid.built_km2, np.nan)
gpkg = config.DATA_PROCESSED / "exposure_grid_1km.gpkg"
grid.to_file(gpkg, layer="exposure_grid_1km", driver="GPKG")
print(len(grid), "cells written to", gpkg.name)"""),
        ("md", "## Exposure raster and map"),
        ("code", """# 0 = not built-up, 1 = built-up not exposed, 2 = built-up 50-100 m from flood, 3 = built-up <= 50 m
ex_cls = np.zeros(district.shape, np.uint8)
ex_cls[built] = 1
ex_cls[built & (d_any <= 100)] = 2
ex_cls[built & (d_any <= MAIN_M)] = 3
ex_cls[~district] = 255
p1 = C.profile() | {"count": 1, "dtype": "uint8", "nodata": 255, "compress": "deflate"}
with rasterio.open(config.OUT_RASTERS / "exposure_any_june2022.tif", "w", **p1) as dst:
    dst.write(ex_cls, 1); dst.descriptions = ("0 other, 1 built not exposed, 2 built 50-100 m, 3 built <=50 m",)

fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), constrained_layout=True)
for ax, col, title in [(axes[0], "exposed_any_km2", "Built-up within 50 m of flooding on any June date"),
                       (axes[1], "exposed_30jun_km2", "Built-up within 50 m of flooding, 30 June (track 77)")]:
    g = grid[grid[col] > 0].assign(ha=lambda x: x[col] * 100)
    grid.plot(ax=ax, color="#f2f0eb", linewidth=0)
    g.plot(ax=ax, column="ha", cmap="OrRd", linewidth=0, legend=True,
           legend_kwds={"label": "built-up near flooding (ha per 1 km² cell)", "shrink": 0.6},
           vmax=g["ha"].quantile(0.99))
    subs.to_crs(prof["crs"]).boundary.plot(ax=ax, color="#555", lw=0.5)
    dist_poly.boundary.plot(ax=ax, color="k", lw=0.8)
    for _, s in subs.to_crs(prof["crs"]).iterrows():
        c = s.geometry.representative_point(); ax.annotate(s.sdtname, (c.x, c.y), ha="center", fontsize=8, color="#333")
    ax.set_title(title); ax.set_axis_off()
fig.savefig(config.OUT_FIGURES / "exposure_grid_1km.png", dpi=150)
plt.show()"""),
        ("code", """fig, ax = plt.subplots(figsize=(8, 4))
e = expo[expo.scenario != "any June date"].copy()
e["date"] = pd.to_datetime(e.scenario.str[:10])
for m, mk in [(30, "v"), (50, "o"), (100, "^")]:
    ax.plot(e.date, e[f"exposed_{m}m_km2"], mk + "-", label=f"within {m} m")
ax.set_ylabel("built-up near flood water (km²)"); ax.grid(alpha=.3); ax.legend()
ax.set_title("Built-up exposure through June 2022 (both tracks)")
fig.autofmt_xdate(); fig.savefig(config.OUT_FIGURES / "exposure_timeseries.png", dpi=150, bbox_inches="tight")
plt.show()"""),
    ],
}


def build(force: bool, only: list[str]) -> None:
    NB_DIR.mkdir(exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        if only and not any(name.startswith(o) for o in only):
            continue
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
    # usage: make_notebooks.py [--force] [prefix ...]   e.g. --force 03
    build("--force" in sys.argv, [a for a in sys.argv[1:] if not a.startswith("--")])
