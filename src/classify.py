"""Local (numpy) flood classification on the downloaded stacks.

Rule per acquisition (after Twele et al. 2016 / UN-SPIDER recommended practice):
  flood = [VH - VH0 < diff_db]  AND  [VH < vh_t]  AND  [HAND < hand_m]  AND  [slope < slope_deg]
          AND NOT permanent water (JRC seasonality >= perm_months), then remove patches < mmu_px.
vh_t is either fixed or found automatically with edge-based Otsu (Donchyts et al. 2016).
Classes: 0 not flooded, 1 flood, 2 permanent water, 255 not observed / outside district.
"""
from __future__ import annotations

import json
from functools import lru_cache

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy import ndimage
from skimage.feature import canny
from skimage.filters import threshold_otsu

import config

STACK_DIR = config.OUT_RASTERS / "stacks"
NODATA = -32768
PIX_KM2 = 1e-4  # 10 m x 10 m


# --------------------------------------------------------------------------- loading
def grid() -> dict:
    return json.loads((config.DATA_PROCESSED / "grid.json").read_text())


def profile() -> dict:
    with rasterio.open(STACK_DIR / "static.tif") as r:
        return r.profile.copy()


def _read(path, bands, scale=1.0):
    """Read named bands. Band order is fixed by floodmap.s1_stack / static_stack; GeoTIFF band
    descriptions are used when present, otherwise the requested order is assumed to be the file order."""
    with rasterio.open(path) as r:
        desc = list(r.descriptions)
        idx = [desc.index(b) + 1 for b in bands] if all(b in desc for b in bands) else list(range(1, len(bands) + 1))
        out = {}
        for b, i in zip(bands, idx):
            a = r.read(i)
            f = a.astype("float32") / scale
            f[a == NODATA] = np.nan
            out[b] = f
    return out


@lru_cache(maxsize=1)
def static() -> dict:
    s = _read(STACK_DIR / "static.tif", ["hand_dm", "slope_ddeg", "jrc_seasonality", "jrc_occurrence", "worldcover"])
    return {
        "hand": s["hand_dm"] / 10, "slope": s["slope_ddeg"] / 10,
        "seasonality": s["jrc_seasonality"], "occurrence": s["jrc_occurrence"],
        "worldcover": s["worldcover"], "district": district_mask(),
    }


def rasterize_gdf(gdf: gpd.GeoDataFrame, values=None, fill=0, dtype="uint8") -> np.ndarray:
    p = profile()
    gdf = gdf.to_crs(p["crs"])
    shapes = zip(gdf.geometry, values if values is not None else [1] * len(gdf))
    return rasterize(shapes, out_shape=(p["height"], p["width"]), transform=p["transform"],
                     fill=fill, dtype=dtype)


@lru_cache(maxsize=1)
def district_mask() -> np.ndarray:
    return rasterize_gdf(gpd.read_file(config.BOUNDARY_FILE)).astype(bool)


def load_s1(date: str, orbit: int) -> dict:
    name = f"s1_{date.replace('-', '')}_t{orbit}.tif"
    return _read(STACK_DIR / name, ["VV", "VH", "VV0", "VH0"], scale=100)


# --------------------------------------------------------------------------- thresholds
def otsu_vh(vh: np.ndarray, hand_ok: np.ndarray, region: np.ndarray, step: int = 2) -> float:
    """Edge-based Otsu: histogram of VH only within ~60 m of land/water edges in flood-prone terrain.
    Computed on a 20 m subsample (step=2) for speed."""
    v = vh[::step, ::step]
    ok = np.isfinite(v) & hand_ok[::step, ::step] & region[::step, ::step]
    filled = np.where(np.isfinite(v), v, -30).clip(-30, 0)
    edges = canny(filled, sigma=1.5, low_threshold=1.0, high_threshold=2.5, mask=ok)
    near = ndimage.binary_dilation(edges, iterations=3) & ok
    sample = v[near]
    return float(threshold_otsu(sample[(sample > -35) & (sample < 0)]))


# --------------------------------------------------------------------------- classification
def remove_small(mask: np.ndarray, min_px: int) -> np.ndarray:
    if min_px <= 1:
        return mask
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_px
    keep[0] = False
    return keep[lab]


def classify(s1: dict, params: dict | None = None, st: dict | None = None) -> tuple[np.ndarray, dict]:
    p = {**config.DEFAULT_PARAMS, **(params or {})}
    st = st or static()
    vh, vh0 = s1["VH"], s1["VH0"]
    observed = np.isfinite(vh) & np.isfinite(vh0) & st["district"]
    hand_ok = np.nan_to_num(st["hand"], nan=999) < p["hand_m"]

    info = {}
    if p["vh_db"] == "otsu":
        t = otsu_vh(vh, hand_ok, observed)
        info["vh_otsu"] = t
        vh_t = t if -26 < t < -15 else p["vh_fallback_db"]
    else:
        vh_t = float(p["vh_db"])
    info["vh_threshold"] = vh_t

    with np.errstate(invalid="ignore"):
        cand = ((vh - vh0) < p["diff_db"]) & (vh < vh_t)
    cand &= hand_ok & (np.nan_to_num(st["slope"], nan=99) < p["slope_deg"])
    perm = np.nan_to_num(st["seasonality"], nan=0) >= p["perm_months"]
    flood = remove_small(cand & ~perm & observed, p["mmu_px"])

    classes = np.zeros(vh.shape, np.uint8)
    classes[flood] = 1
    classes[perm & observed] = 2
    classes[~observed] = 255
    info.update({k: v for k, v in p.items() if k != "vh_db"})
    return classes, info


# --------------------------------------------------------------------------- statistics / io
def areas_km2(classes: np.ndarray, region: np.ndarray | None = None) -> dict:
    sel = classes if region is None else classes[region]
    return {
        "observed_km2": float(np.count_nonzero(sel != 255) * PIX_KM2),
        "flood_km2": float(np.count_nonzero(sel == 1) * PIX_KM2),
        "permanent_water_km2": float(np.count_nonzero(sel == 2) * PIX_KM2),
    }


def write_classes(classes: np.ndarray, path) -> None:
    p = profile() | {"count": 1, "dtype": "uint8", "nodata": 255, "compress": "deflate", "predictor": 1}
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(classes, 1)
        dst.set_band_description(1, "class: 0 dry, 1 flood, 2 permanent water")
