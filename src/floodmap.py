"""Earth Engine side: Sentinel-1 preprocessing and export of analysis-ready stacks.

Earth Engine does data access and the heavy per-scene work:
  * border-noise mask and Lee speckle filter (linear power, 7x7, ENL 4.4) for every scene,
  * dry-season baseline = median of filtered scenes from the SAME relative orbit,
  * terrain / water / land-cover layers (MERIT HAND, SRTM slope, JRC GSW, ESA WorldCover).
Stacks are downloaded once on a fixed 10 m UTM 46N grid (src/fetch_stacks.py); flood
classification, thresholds and statistics then run locally (src/classify.py).
"""
from __future__ import annotations

import ee

import config

NODATA = -32768  # int16 nodata for exported stacks
DB_SCALE = 100   # dB values are stored as int16 = round(dB * 100)


# --------------------------------------------------------------------------- inputs
def s1_track(aoi: ee.Geometry, start, end, rel_orbit: int) -> ee.ImageCollection:
    return (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("relativeOrbitNumber_start", rel_orbit))
        .select(["VV", "VH"])
    )


# --------------------------------------------------------------------------- preprocessing
def _to_linear(db: ee.Image) -> ee.Image:
    return ee.Image(10).pow(db.divide(10))


def _to_db(lin: ee.Image) -> ee.Image:
    return lin.log10().multiply(10)


def lee_filter(lin: ee.Image, radius_px: int = 3, enl: float = 4.4) -> ee.Image:
    """Classic Lee (1980) filter on linear intensity (7x7 window for radius 3)."""
    names = lin.bandNames()
    kernel = ee.Kernel.square(radius_px, "pixels")
    mean = lin.reduceNeighborhood(ee.Reducer.mean(), kernel).rename(names)
    var = lin.reduceNeighborhood(ee.Reducer.variance(), kernel).rename(names)
    ci2 = var.divide(mean.pow(2))
    w = ee.Image(1).subtract(ee.Image(1.0 / enl).divide(ci2)).max(0)
    return mean.add(w.multiply(lin.subtract(mean)))


def preprocess(img: ee.Image) -> ee.Image:
    """Mask border noise, speckle-filter; returns VV/VH in dB with the scene footprint."""
    valid = img.select("VV").gt(-30).And(img.select("VH").gt(-40))
    lin = _to_linear(img.updateMask(valid))
    out = _to_db(lee_filter(lin)).rename(["VV", "VH"])
    return out.copyProperties(img, ["system:time_start", "relativeOrbitNumber_start", "orbitProperties_pass"])


def baseline(aoi: ee.Geometry, rel_orbit: int, window=config.BASELINE_DRY) -> ee.Image:
    col = s1_track(aoi, *window, rel_orbit).map(preprocess)
    return col.median().set("n_scenes", col.size())


def event_image(aoi: ee.Geometry, date: str, rel_orbit: int) -> ee.Image:
    d = ee.Date(date)
    col = s1_track(aoi, d, d.advance(1, "day"), rel_orbit).map(preprocess)
    return col.mosaic().set("n_scenes", col.size())


# --------------------------------------------------------------------------- stacks
def s1_stack(aoi: ee.Geometry, date: str, rel_orbit: int) -> ee.Image:
    """int16 stack (dB*100): VV, VH (event) and VV0, VH0 (dry baseline, same track)."""
    ev = event_image(aoi, date, rel_orbit)
    b0 = baseline(aoi, rel_orbit).rename(["VV0", "VH0"])
    stack = ev.addBands(b0).multiply(DB_SCALE).round()
    return (stack.unmask(NODATA).toInt16()
            .set({"date": date, "rel_orbit": rel_orbit, "db_scale": DB_SCALE, "nodata": NODATA}))


def static_stack() -> ee.Image:
    """int16 stack: HAND (m*10), slope (deg*10), JRC seasonality (months), JRC occurrence (%),
    WorldCover 2021 class code.

    Slope comes from the MERIT DEM (90 m, tree/building height bias removed). SRTM 30 m slope is
    dominated by canopy/building noise on the Nagaon floodplain (>10 % of HAND < 5 m land shows
    slope >= 5 deg), which would wrongly exclude flooded pixels."""
    merit = ee.Image("MERIT/Hydro/v1_0_1")
    hand = merit.select("hnd").multiply(10).rename("hand_dm")
    slope = ee.Terrain.slope(merit.select("elv")).multiply(10).rename("slope_ddeg")
    gsw = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    seas = gsw.select("seasonality").unmask(0).rename("jrc_seasonality")
    occ = gsw.select("occurrence").unmask(0).rename("jrc_occurrence")
    wc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").rename("worldcover")
    return (hand.addBands([slope, seas, occ, wc]).round()
            .unmask(NODATA).toInt16())
