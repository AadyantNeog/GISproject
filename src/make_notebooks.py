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
        ("code", """dist_to_flood_m = C.distance_to_flood_m  # metres to nearest flood pixel; +inf if no flood

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
Hc, Wc = -(-H // k), -(-W // k)  # ceil: keep partial cells at the east/south edges
def block_sum(a):
    padded = np.zeros((Hc * k, Wc * k), dtype=np.float64)
    padded[:H, :W] = a
    return padded.reshape(Hc, k, Wc, k).sum(axis=(1, 3)) * C.PIX_KM2

exp_any = block_sum(built & (obs > 0) & (d_any <= MAIN_M))
built_c = block_sum(built)
peak = ("2022-06-30", 77)
exp_peak = block_sum(built & (maps[peak] != 255) & (dist[peak] <= MAIN_M))
flood_any_c = block_sum(any_flood)
cells = []
for i in range(Hc):
    for j in range(Wc):
        x0 = t.c + j * k * t.a; y1 = t.f + i * k * t.e
        x1 = min(x0 + k * t.a, t.c + W * t.a); y0 = max(y1 + k * t.e, t.f + H * t.e)  # clip edge cells to grid
        cells.append(box(x0, y0, x1, y1))
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
    "04_sensitivity.ipynb": [
        ("md", "# 04 · Sensitivity of flood extent and exposure to detection settings\n\n"
               "Research question (iii). One parameter is varied at a time around the defaults "
               "(VH drop −3 dB, VH below the per-scene Otsu value, HAND < 15 m, slope < 5°, JRC permanent "
               "water ≥ 10 months, patches ≥ 8 px). To isolate each effect the Otsu value is held fixed at its "
               "default for the date. Three dates: **16 June** (track 41 — same scene as the MBRSC reference), "
               "**18 June** (track 77 — nearest full-coverage scene to the ALOS-2 reference of 22 June) and "
               "**30 June** (track 77, largest extent). Outputs: flood area, built-up within 50 m, and "
               "agreement (F1) with the reference where one exists."),
        ("code", """import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path.cwd().parent / "src"))
import numpy as np, pandas as pd, geopandas as gpd, matplotlib.pyplot as plt
import config, classify as C

st = C.static()
built = (st["worldcover"] == 50) & st["district"]
REF = config.DATA_PROCESSED / "reference_nagaon.gpkg"
refs = {"mbrsc_s1_20220616": C.rasterize_gdf(gpd.read_file(REF, layer="mbrsc_s1_20220616")).astype(bool),
        "eosrs_alos2_20220622": C.rasterize_gdf(gpd.read_file(REF, layer="eosrs_alos2_20220622")).astype(bool)}
DATES = {("2022-06-16", 41): "mbrsc_s1_20220616",
         ("2022-06-18", 77): "eosrs_alos2_20220622",
         ("2022-06-30", 77): None}

SWEEPS = {
    "diff_db":     [-1.0, -1.5, -2.0, -2.5, -3.0, -3.5, -4.0, -5.0, -6.0],
    "vh_db":       [-17.0, -18.0, -19.0, -20.0, -21.0, -22.0, -23.0, -24.0],
    "hand_m":      [5, 10, 15, 20, 30, 1000],
    "slope_deg":   [2, 3, 5, 10, 90],
    "perm_months": [13, 12, 10, 6, 3, 1],
    "mmu_px":      [1, 4, 8, 16, 30, 100],
    "pol":         ["VH", "VV"],
}
DEFAULTS = {k: config.DEFAULT_PARAMS[k] for k in SWEEPS if k in config.DEFAULT_PARAMS}"""),
        ("code", """rows = []
t0 = time.time()
for (date, orb), ref_name in DATES.items():
    s1 = C.load_s1(date, orb)
    _, info = C.classify(s1, st=st)              # default run -> Otsu value for this date
    otsu_t = info["vh_threshold"]
    for param, values in SWEEPS.items():
        if param == "vh_db":                     # include the exact Otsu value as the default row
            values = sorted(set(values) | {round(otsu_t, 4)})
        for v in values:
            prm = {"vh_db": otsu_t, param: v}
            if param == "pol" and v == "VV":
                prm["vh_db"] = "otsu"           # VV needs its own automatic threshold
            cl, inf = C.classify(s1, prm, st=st)
            r = {"date": date, "track": orb, "param": param, "value": v,
                 "is_default": (v == round(otsu_t, 4)) if param == "vh_db" else (v == DEFAULTS.get(param)),
                 "vh_threshold": inf["vh_threshold"], "flood_km2": C.areas_km2(cl)["flood_km2"],
                 **C.built_exposed_km2(cl, built, (50,))}
            if ref_name:
                a = C.agreement(cl, refs[ref_name])
                r.update({"reference": ref_name, "f1": a["f1"], "precision": a["precision"], "recall": a["recall"]})
            rows.append(r)
    print(date, "otsu", round(otsu_t, 2), f"{time.time() - t0:.0f}s")
    del s1
sens = pd.DataFrame(rows)
sens.to_csv(config.OUT_TABLES / "sensitivity_one_at_a_time.csv", index=False)
sens.head()"""),
        ("md", "## One-at-a-time results"),
        ("code", """labels = {"diff_db": "VH drop threshold (dB)", "vh_db": "absolute VH threshold (dB)",
          "hand_m": "HAND exclusion (m; 1000 = off)", "slope_deg": "slope exclusion (°; 90 = off)",
          "perm_months": "permanent water: JRC months ≥ (13 = off)", "mmu_px": "minimum patch (px)",
          "pol": "polarisation"}
def panel_plot(metric, ylabel, fname, dates=DATES):
    fig, axes = plt.subplots(2, 4, figsize=(17, 8), constrained_layout=True)
    for ax, param in zip(axes.ravel(), SWEEPS):
        for (date, orb) in dates:
            d = sens[(sens.param == param) & (sens.date == date)]
            if metric not in d or d[metric].isna().all():
                continue
            x = d["value"].astype(str) if param == "pol" else d["value"]
            ax.plot(x, d[metric], "o-", ms=4, label=f"{date} t{orb}")
            dd = d[d.is_default]
            ax.plot(dd["value"].astype(str) if param == "pol" else dd["value"], dd[metric], "k*", ms=11, zorder=5)
        ax.set_title(labels[param], fontsize=10); ax.grid(alpha=.3)
    axes.ravel()[-1].axis("off")
    axes.ravel()[0].legend(fontsize=8)
    fig.supylabel(ylabel); fig.suptitle(f"Sensitivity of {ylabel} (★ = default setting)")
    fig.savefig(config.OUT_FIGURES / fname, dpi=150); plt.show()

panel_plot("flood_km2", "flooded area (km²)", "sensitivity_flood_area.png")"""),
        ("code", """panel_plot("exposed_50m_km2", "built-up within 50 m of flood (km²)", "sensitivity_exposure.png")"""),
        ("code", """panel_plot("f1", "F1 agreement with reference", "sensitivity_f1.png",
           dates=[k for k, v in DATES.items() if v])"""),
        ("md", "## Joint sweep of the two main thresholds (18 June, track 77)"),
        ("code", """s1 = C.load_s1("2022-06-18", 77)
diffs = [-1.5, -2.0, -2.5, -3.0, -3.5, -4.0, -5.0]
vhs = [-17.0, -18.0, -19.0, -20.0, -21.0, -22.0, -23.0]
area = np.zeros((len(diffs), len(vhs))); f1 = np.zeros_like(area)
for i, dv in enumerate(diffs):
    for j, vv in enumerate(vhs):
        cl, _ = C.classify(s1, {"diff_db": dv, "vh_db": vv}, st=st)
        area[i, j] = C.areas_km2(cl)["flood_km2"]
        f1[i, j] = C.agreement(cl, refs["eosrs_alos2_20220622"])["f1"]
del s1
grid2 = pd.DataFrame([{"diff_db": d, "vh_db": v, "flood_km2": area[i, j], "f1_alos2": f1[i, j]}
                      for i, d in enumerate(diffs) for j, v in enumerate(vhs)])
grid2.to_csv(config.OUT_TABLES / "sensitivity_joint_18jun.csv", index=False)
fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
for ax, z, title, fmt in [(axes[0], area, "flooded area (km²)", "{:.0f}"), (axes[1], f1, "F1 vs ALOS-2 (22 Jun)", "{:.2f}")]:
    im = ax.imshow(z, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(vhs)), vhs); ax.set_yticks(range(len(diffs)), diffs)
    ax.set_xlabel("absolute VH threshold (dB)"); ax.set_ylabel("VH drop threshold (dB)"); ax.set_title(title)
    for i in range(len(diffs)):
        for j in range(len(vhs)):
            ax.text(j, i, fmt.format(z[i, j]), ha="center", va="center", fontsize=7,
                    color="w" if z[i, j] < z.mean() else "k")
    fig.colorbar(im, ax=ax, shrink=0.8)
fig.savefig(config.OUT_FIGURES / "sensitivity_joint_18jun.png", dpi=150); plt.show()"""),
        ("md", "## Summary: plausible range\n\n"
               "Range of results when the two main thresholds vary over commonly used values "
               "(drop −2 to −4 dB, VH −19 to −22 dB), plus each one-at-a-time sweep's spread relative to the default."),
        ("code", """plaus = grid2[(grid2.diff_db.between(-4, -2)) & (grid2.vh_db.between(-22, -19))]
print(f"18 June flood area over plausible thresholds: {plaus.flood_km2.min():.0f}-{plaus.flood_km2.max():.0f} km2 "
      f"(default {sens[(sens.date=='2022-06-18') & (sens.param=='diff_db') & sens.is_default].flood_km2.iloc[0]:.0f})")
summ = []
for (date, orb) in DATES:
    for param in SWEEPS:
        d = sens[(sens.date == date) & (sens.param == param)]
        base = d[d.is_default]
        if base.empty:
            continue
        b = base.iloc[0]
        summ.append({"date": date, "param": param,
                     "flood_min_km2": d.flood_km2.min(), "flood_max_km2": d.flood_km2.max(),
                     "flood_range_pct_of_default": 100 * (d.flood_km2.max() - d.flood_km2.min()) / b.flood_km2,
                     "exposed50_min_km2": d.exposed_50m_km2.min(), "exposed50_max_km2": d.exposed_50m_km2.max()})
summary = pd.DataFrame(summ).round(1)
summary.to_csv(config.OUT_TABLES / "sensitivity_summary.csv", index=False)
summary.pivot(index="param", columns="date", values="flood_range_pct_of_default")"""),
    ],
    "05_validation.ipynb": [
        ("md", "# 05 · Agreement with reference flood maps and published estimates\n\n"
               "References available as GIS layers (Sentinel Asia):\n"
               "* **MBRSC**, Sentinel-1, 16 June 2022 — same scene as our 16 June map, so not independent of the sensor.\n"
               "* **EOS-RS Flood Proxy Map**, ALOS-2 PALSAR-2 (L-band), 22 June 2022 — independent sensor; "
               "4 days after our 18 June scene and 6 days before 28 June.\n"
               "* **EOS-RS**, Sentinel-1, 18 May 2022 — the earlier May flood wave (checks the baseline choice).\n\n"
               "Published areas: Irukumati et al. (2025), same district and dates, including the NRSC areas they used as reference.\n\n"
               "Caveat: the reference products are rapid-mapping outputs with their own errors (they are usually "
               "conservative), so disagreement is not all our error."),
        ("code", """import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent / "src"))
import numpy as np, pandas as pd, geopandas as gpd, rasterio, matplotlib.pyplot as plt
from scipy import stats
import config, classify as C

st = C.static(); district = st["district"]
REF = config.DATA_PROCESSED / "reference_nagaon.gpkg"
ref = {n: C.rasterize_gdf(gpd.read_file(REF, layer=n)).astype(bool) & district
       for n in ["mbrsc_s1_20220616", "eosrs_alos2_20220622", "eosrs_s1_20220518"]}
maps = {}
for date, orb in config.EVENT_DATES:
    with rasterio.open(config.OUT_RASTERS / f"flood_{date.replace('-', '')}_t{orb}.tif") as r:
        maps[(date, orb)] = r.read(1)
# June envelope: flooded on any date (observed on at least one date)
env = np.full(district.shape, 255, np.uint8)
anyobs = np.logical_or.reduce([m != 255 for m in maps.values()])
env[anyobs] = 0
env[np.logical_or.reduce([m == 1 for m in maps.values()])] = 1
for k in ref: print(k, round(ref[k].sum() * C.PIX_KM2, 1), "km2 in district")"""),
        ("md", "## 1 · Pixel agreement (10 m)"),
        ("code", """pairs = [("mbrsc_s1_20220616", "2022-06-16 t41", maps[("2022-06-16", 41)]),
         ("eosrs_alos2_20220622", "2022-06-18 t77", maps[("2022-06-18", 77)]),
         ("eosrs_alos2_20220622", "2022-06-28 t41", maps[("2022-06-28", 41)]),
         ("eosrs_alos2_20220622", "June envelope (any date)", env)]
pix = pd.DataFrame([{"reference": r, "ours": lab, **C.agreement(cl, ref[r])} for r, lab, cl in pairs]).round(3)
pix.to_csv(config.OUT_TABLES / "validation_pixel.csv", index=False)
pix"""),
        ("md", "## 2 · Agreement at coarser scales (tolerates small geolocation and edge differences)\n\n"
               "Flood fraction per cell, ours vs reference; Pearson r and mean absolute difference."),
        ("code", """def block_mean(a, k):
    H, W = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return a[:H, :W].reshape(H // k, k, W // k, k).mean(axis=(1, 3))

rows = []
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
for ax, (r, lab, cl) in zip(axes, pairs[:3]):
    ok = (cl != 255) & district
    for k in (10, 50, 100):  # 100 m, 500 m, 1 km
        valid = block_mean(ok.astype(np.float32), k) > 0.9
        fo = block_mean(((cl == 1) & ok).astype(np.float32), k)[valid]
        fr = block_mean((ref[r] & ok).astype(np.float32), k)[valid]
        rows.append({"reference": r, "ours": lab, "cell_m": k * 10, "n_cells": int(valid.sum()),
                     "pearson_r": stats.pearsonr(fo, fr)[0], "mean_abs_diff_pct": 100 * np.abs(fo - fr).mean()})
        if k == 50:
            ax.hexbin(fr * 100, fo * 100, gridsize=40, bins="log", cmap="Blues", mincnt=1)
            ax.plot([0, 100], [0, 100], "k--", lw=0.8)
            ax.set_xlabel(f"{r} flood % (500 m cells)"); ax.set_ylabel(f"ours {lab} flood %")
            ax.set_title(f"r = {rows[-1]['pearson_r']:.2f}")
fig.savefig(config.OUT_FIGURES / "validation_cell_scatter.png", dpi=150); plt.show()
cells = pd.DataFrame(rows).round(3)
cells.to_csv(config.OUT_TABLES / "validation_cells.csv", index=False)
cells"""),
        ("md", "## 3 · Where do the maps disagree? (by land cover and by JRC water history)\n\n"
               "Commission = ours only; omission = reference only. Land cover from WorldCover 2021."),
        ("code", """WC = {10: "tree cover", 20: "shrubland", 30: "grassland", 40: "cropland", 50: "built-up",
      60: "bare", 80: "permanent water", 90: "herbaceous wetland"}
wc = np.nan_to_num(st["worldcover"], nan=0).astype(int)
occ = np.nan_to_num(st["occurrence"], nan=0)
recs = []
for r, lab, cl in pairs[:3]:
    ok = (cl != 255) & district
    ours, refm = (cl == 1) & ok, ref[r] & ok
    for name, m in [("agree", ours & refm), ("ours only", ours & ~refm), ("reference only", ~ours & refm)]:
        row = {"reference": r, "ours": lab, "set": name, "total_km2": m.sum() * C.PIX_KM2,
               "jrc_ever_water_pct": 100 * np.count_nonzero(m & (occ > 0)) / max(m.sum(), 1)}
        for code, cname in WC.items():
            row[cname] = np.count_nonzero(m & (wc == code)) * C.PIX_KM2
        recs.append(row)
dis = pd.DataFrame(recs).round(1)
dis.to_csv(config.OUT_TABLES / "validation_disagreement_landcover.csv", index=False)
dis"""),
        ("md", "## 4 · Sub-district totals"),
        ("code", """subs = gpd.read_file(config.DATA_PROCESSED / "nagaon_2022_subdistricts.geojson").reset_index(drop=True)
sub_id = C.rasterize_gdf(subs, values=range(1, len(subs) + 1)); n = len(subs) + 1
rows = []
for r, lab, cl in pairs[:3]:
    ok = (cl != 255) & district
    o = np.bincount(sub_id[(cl == 1) & ok], minlength=n)[1:] * C.PIX_KM2
    f = np.bincount(sub_id[ref[r] & ok], minlength=n)[1:] * C.PIX_KM2
    rho = stats.spearmanr(o, f)[0]
    for name, a, b in zip(subs.sdtname, o, f):
        rows.append({"reference": r, "ours": lab, "subdistrict": name, "ours_km2": a, "ref_km2": b, "spearman_rho_all": rho})
subcmp = pd.DataFrame(rows).round(2)
subcmp.to_csv(config.OUT_TABLES / "validation_subdistrict.csv", index=False)
subcmp.pivot_table(index="subdistrict", columns=["reference", "ours"], values=["ours_km2", "ref_km2"]).round(1)"""),
        ("code", """subcmp.groupby(["reference", "ours"]).spearman_rho_all.first().round(2)"""),
        ("md", "## 5 · Published estimates for the same district and dates\n\n"
               "From Irukumati et al. (2025), Table 3 and text. The NRSC 30 June value (597.32 km²) is "
               "confirmed in the paper's discussion text. For Random Forest VV on 18 June the paper gives "
               "395.56 km² in the text (p. 11) but 295.56 km² in Table 3 (p. 13); the text value is used here."),
        ("code", """areas = pd.read_csv(config.OUT_TABLES / "flood_area_by_date.csv")
ours18 = areas.query("date == '2022-06-18'").flood_km2.iloc[0]
ours30 = areas.query("date == '2022-06-30'").flood_km2.iloc[0]
pub = pd.DataFrame([
    ("NRSC reference (as cited by Irukumati et al.)", 413.28, 597.32, "Table 3; 30 Jun also in discussion text"),
    ("Irukumati et al.: Random Forest, VV", 395.56, 565.27, "18 Jun from text p.11; Table 3 gives 295.56"),
    ("Irukumati et al.: Random Forest, VH", 383.19, 583.21, ""),
    ("Irukumati et al.: Random Forest, VV+VH", 400.29, 592.12, ""),
    ("Irukumati et al.: K-means, VV", 413.28, 613.23, ""),
    ("Irukumati et al.: K-means, VH", 389.24, 592.64, ""),
    ("Irukumati et al.: K-means, VV+VH", 401.78, 551.93, ""),
    ("This study (VH change detection, Otsu)", ours18, ours30, ""),
], columns=["source", "18 Jun 2022 (km2)", "30 Jun 2022 (km2)", "note"])
pub.to_csv(config.OUT_TABLES / "validation_published_areas.csv", index=False)
pub.round(1)"""),
        ("md", "## 6 · May flood wave and baseline choice\n\n"
               "Nagaon flooded in mid-May 2022. Our baseline uses January–mid-April scenes only. How much of the "
               "18 May flood area reappears in June, and how much early-June flood is residual May water?"),
        ("code", """may = ref["eosrs_s1_20220518"]
rows = []
for (date, orb), cl in maps.items():
    ok = cl != 255
    rows.append({"date": date, "track": orb,
                 "flood_km2": np.count_nonzero(cl == 1) * C.PIX_KM2,
                 "of_which_in_may_flood_km2": np.count_nonzero((cl == 1) & may) * C.PIX_KM2,
                 "may_flood_reflooded_pct": 100 * np.count_nonzero((cl == 1) & may) / max(np.count_nonzero(may & ok), 1)})
mayc = pd.DataFrame(rows).round(1)
mayc.to_csv(config.OUT_TABLES / "validation_may_overlap.csv", index=False)
mayc"""),
    ],
    "06_maps.ipynb": [
        ("md", "# 06 · Report maps\n\nPublication-style figures (scale bar, north arrow, legend) saved to `outputs/figures/map_*.png`. "
               "The same layers are styled for QGIS in `qgis/` if you prefer to lay out maps there."),
        ("code", """import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent / "src"))
import numpy as np, pandas as pd, geopandas as gpd, rasterio, matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch, Rectangle
from pyproj import Transformer
import config, classify as C

CRS = config.CRS_METRIC
prof = C.profile(); t = prof["transform"]
EXT = [t.c, t.c + t.a * prof["width"], t.f + t.e * prof["height"], t.f]
district = gpd.read_file(config.BOUNDARY_FILE).to_crs(CRS)
subs = gpd.read_file(config.DATA_PROCESSED / "nagaon_2022_subdistricts.geojson").to_crs(CRS)
assam = gpd.read_file(config.DATA_RAW / "boundary" / "datta07" / "ASSAM_DISTRICTS.geojson").to_crs(CRS)
st = C.static()

def scalebar(ax, length_km=10, loc=(0.06, 0.05)):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    x = x0 + loc[0] * (x1 - x0); y = y0 + loc[1] * (y1 - y0); L = length_km * 1000
    for i in range(2):
        ax.add_patch(Rectangle((x + i * L / 2, y), L / 2, (y1 - y0) * 0.008, fc="k" if i == 0 else "w", ec="k", lw=0.6, zorder=10))
    for frac, lab in [(0, "0"), (0.5, f"{length_km // 2}"), (1, f"{length_km} km")]:
        ax.text(x + frac * L, y + (y1 - y0) * 0.018, lab, ha="center", fontsize=8, zorder=10)

def north(ax, loc=(0.94, 0.88)):
    ax.annotate("N", xy=loc, xytext=(loc[0], loc[1] - 0.08), xycoords="axes fraction", ha="center", fontsize=11,
                fontweight="bold", arrowprops=dict(arrowstyle="-|>", lw=1.5, color="k"))

def lonlat_ticks(ax, step=0.2):
    inv = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True); fwd = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    lo0, la0 = inv.transform(x0, y0); lo1, la1 = inv.transform(x1, y1)
    lons = np.arange(np.ceil(lo0 / step) * step, lo1, step); lats = np.arange(np.ceil(la0 / step) * step, la1, step)
    yc = (y0 + y1) / 2; xc = (x0 + x1) / 2
    ax.set_xticks([fwd.transform(l, inv.transform(xc, yc)[1])[0] for l in lons], [f"{l:.1f}°E" for l in lons], fontsize=7)
    ax.set_yticks([fwd.transform(inv.transform(xc, yc)[0], l)[1] for l in lats], [f"{l:.1f}°N" for l in lats], fontsize=7)
    ax.tick_params(length=2)

def frame(ax):
    ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3]); lonlat_ticks(ax)
    ax.set_xlabel(""); ax.set_ylabel("")

def outline(ax, labels=True):
    subs.boundary.plot(ax=ax, color="#666", lw=0.4, zorder=4)
    district.boundary.plot(ax=ax, color="k", lw=0.9, zorder=4)
    if labels:
        for _, s in subs.iterrows():
            c = s.geometry.representative_point()
            ax.annotate(s.sdtname, (c.x, c.y), ha="center", fontsize=8, color="#222",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.6))"""),
        ("md", "## Map 1 · Study area"),
        ("code", """fig = plt.figure(figsize=(12, 8.5))
ax = fig.add_axes([0.05, 0.05, 0.68, 0.9])
assam.plot(ax=ax, color="#f4f2ee", edgecolor="#bbb", lw=0.5)
hand = np.where(st["district"], np.clip(st["hand"], 0, 40), np.nan)
im = ax.imshow(hand[::4, ::4], extent=EXT, cmap="YlGnBu_r", vmin=0, vmax=40, zorder=2)
perm = np.where(st["seasonality"] >= 10, 1, np.nan)
ax.imshow(perm[::2, ::2], extent=EXT, cmap=ListedColormap(["#08306b"]), interpolation="nearest", zorder=3)
outline(ax)
for _, d in assam.iterrows():
    if d.dtname in ("Morigaon", "Hojai", "Karbi Anglong", "Sonitpur", "Golaghat", "Biswanath", "Darrang", "West Karbi Anglong"):
        c = d.geometry.representative_point()
        if EXT[0] < c.x < EXT[1] and EXT[2] < c.y < EXT[3]:
            ax.annotate(d.dtname.upper(), (c.x, c.y), ha="center", fontsize=7, color="#888")
frame(ax); scalebar(ax); north(ax)
cb = fig.colorbar(im, ax=ax, shrink=0.45, pad=0.01); cb.set_label("height above nearest drainage (m)")
ax.set_title("Study area: Nagaon district (June 2022 extent) and census sub-districts")
ax.legend(handles=[Patch(color="#08306b", label="permanent water (JRC ≥ 10 months)")], loc="upper left", fontsize=8)
# inset: Assam with Nagaon highlighted
ia = fig.add_axes([0.74, 0.55, 0.25, 0.35])
assam.plot(ax=ia, color="#e8e5df", edgecolor="#999", lw=0.3)
district.plot(ax=ia, color="#d7301f")
ia.set_title("Assam", fontsize=9); ia.set_axis_off()
fig.savefig(config.OUT_FIGURES / "map_study_area.png", dpi=200, bbox_inches="tight"); plt.show()"""),
        ("md", "## Map 2 · Flood extent on the two track-77 event dates"),
        ("code", """cmap = ListedColormap(["#ece9e2", "#2171b5", "#08306b"]); norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3)
areas = pd.read_csv(config.OUT_TABLES / "flood_area_by_date.csv")
fig, axes = plt.subplots(1, 2, figsize=(16, 7.5), constrained_layout=True)
for ax, (date, orb) in zip(axes, [("2022-06-18", 77), ("2022-06-30", 77)]):
    with rasterio.open(config.OUT_RASTERS / f"flood_{date.replace('-', '')}_t{orb}.tif") as r:
        cl = r.read(1).astype(float)
    cl[cl == 255] = np.nan
    ax.imshow(cl[::3, ::3], extent=EXT, cmap=cmap, norm=norm, interpolation="nearest", zorder=2)
    outline(ax); frame(ax); scalebar(ax); north(ax)
    a = areas.query("date == @date").flood_km2.iloc[0]
    ax.set_title(f"Sentinel-1 flood extent, {date} (track {orb}, descending): {a:.0f} km²")
axes[1].legend(handles=[Patch(color="#2171b5", label="flood (event-related)"), Patch(color="#08306b", label="permanent water"),
                        Patch(color="#ece9e2", label="not flooded")], loc="lower right", fontsize=9)
fig.savefig(config.OUT_FIGURES / "map_flood_extent.png", dpi=200, bbox_inches="tight"); plt.show()"""),
        ("md", "## Map 3 · How persistent was the flooding? (number of June dates flooded)"),
        ("code", """with rasterio.open(config.OUT_RASTERS / "flood_frequency_june2022.tif") as r:
    freq = r.read(1).astype(float)
freq[(freq == 255) | (freq == 0)] = np.nan
fig, ax = plt.subplots(figsize=(11, 8))
district.plot(ax=ax, color="#ece9e2")
cm = ListedColormap(["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b"])
im = ax.imshow(freq[::3, ::3], extent=EXT, cmap=cm, norm=BoundaryNorm(np.arange(0.5, 7.5), 6), interpolation="nearest", zorder=2)
outline(ax); frame(ax); scalebar(ax); north(ax)
cb = fig.colorbar(im, ax=ax, shrink=0.6, ticks=range(1, 7)); cb.set_label("number of the six June acquisitions mapped as flooded")
ax.set_title("Flood persistence, 4–30 June 2022")
fig.savefig(config.OUT_FIGURES / "map_flood_frequency.png", dpi=200, bbox_inches="tight"); plt.show()"""),
        ("md", "## Map 4 · Built-up exposure (any June date), with a pixel-level zoom near Raha"),
        ("code", """grid = gpd.read_file(config.DATA_PROCESSED / "exposure_grid_1km.gpkg")
grid["ha"] = grid.exposed_any_km2 * 100
with rasterio.open(config.OUT_RASTERS / "exposure_any_june2022.tif") as r:
    ex = r.read(1).astype(float)
with rasterio.open(config.OUT_RASTERS / "flood_frequency_june2022.tif") as r:
    fq = r.read(1)
fig = plt.figure(figsize=(17, 8))
ax = fig.add_axes([0.03, 0.05, 0.55, 0.9])
grid.plot(ax=ax, color="#f4f2ee", lw=0)
g = grid[grid.ha > 0]
g.plot(ax=ax, column="ha", cmap="OrRd", lw=0, legend=True, vmax=g.ha.quantile(0.99),
       legend_kwds={"label": "built-up within 50 m of flooding (ha per 1 km² cell)", "shrink": 0.55})
outline(ax); frame(ax); scalebar(ax); north(ax)
# zoom window near Raha town
fx, fy = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform(92.515, 26.235)
W = 3000
ax.add_patch(Rectangle((fx - W, fy - W), 2 * W, 2 * W, fill=False, ec="#08519c", lw=1.5))
ax.set_title("Built-up land within 50 m of mapped flooding on any June 2022 date")
z = fig.add_axes([0.62, 0.1, 0.36, 0.8])
c0 = int((fx - W - t.c) / t.a); c1 = int((fx + W - t.c) / t.a)
r0 = int((t.f - (fy + W)) / -t.e); r1 = int((t.f - (fy - W)) / -t.e)
sub_fq = fq[r0:r1, c0:c1].astype(float); sub_fq[(sub_fq == 0) | (sub_fq == 255)] = np.nan
sub_ex = ex[r0:r1, c0:c1]
zext = [fx - W, fx + W, fy - W, fy + W]
z.imshow(np.zeros_like(sub_fq), extent=zext, cmap=ListedColormap(["#f4f2ee"]))
z.imshow(sub_fq, extent=zext, cmap="Blues", vmin=0, vmax=6, interpolation="nearest")
excol = np.full(sub_ex.shape + (4,), 0.0)
excol[sub_ex == 1] = (0.55, 0.55, 0.55, 1); excol[sub_ex == 2] = (0.99, 0.68, 0.38, 1); excol[sub_ex == 3] = (0.84, 0.19, 0.12, 1)
z.imshow(excol, extent=zext, interpolation="nearest")
z.set_xticks([]); z.set_yticks([]); z.set_title("Zoom near Raha (6 × 6 km, 10 m pixels)")
z.legend(handles=[Patch(color="#d7301f", label="built-up ≤ 50 m from flood"), Patch(color="#fdae61", label="built-up 50–100 m"),
                  Patch(color="#8c8c8c", label="built-up > 100 m"), Patch(color="#6baed6", label="flooded (darker = more dates)")],
         loc="lower left", fontsize=8, framealpha=0.9)
z.set_xlim(zext[0], zext[1]); z.set_ylim(zext[2], zext[3]); scalebar(z, length_km=2, loc=(0.6, 0.93))
fig.savefig(config.OUT_FIGURES / "map_exposure.png", dpi=200, bbox_inches="tight"); plt.show()"""),
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
