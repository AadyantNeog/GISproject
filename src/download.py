"""Fixed analysis grid + tiled download of Earth Engine images to local GeoTIFFs."""
from __future__ import annotations

import io
import math
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
import rasterio
import requests
from pyproj import Transformer
from rasterio.merge import merge

import config


def grid_for(aoi: ee.Geometry, scale: float = 10, crs: str = config.CRS_METRIC, pad: float = 200) -> dict:
    """Pixel-aligned grid covering the AOI bounding box (+pad metres) in `crs`."""
    coords = aoi.bounds(maxError=10).coordinates().get(0).getInfo()
    lons, lats = [c[0] for c in coords], [c[1] for c in coords]
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = t.transform([min(lons), max(lons), min(lons), max(lons)],
                         [min(lats), min(lats), max(lats), max(lats)])
    x0 = math.floor((min(xs) - pad) / scale) * scale
    x1 = math.ceil((max(xs) + pad) / scale) * scale
    y0 = math.floor((min(ys) - pad) / scale) * scale
    y1 = math.ceil((max(ys) + pad) / scale) * scale
    w, h = int(round((x1 - x0) / scale)), int(round((y1 - y0) / scale))
    return {"crs": crs, "scale": scale, "x0": x0, "y1": y1, "width": w, "height": h,
            "transform": [scale, 0, x0, 0, -scale, y1], "dimensions": f"{w}x{h}"}


def _fetch(img: ee.Image, grid: dict, col0: int, row0: int, w: int, h: int, out: Path,
           retries: int = 6) -> Path:
    s = grid["scale"]
    x0, y1 = grid["x0"] + col0 * s, grid["y1"] - row0 * s
    url = img.getDownloadURL({
        "format": "GEO_TIFF", "crs": grid["crs"],
        "crs_transform": [s, 0, x0, 0, -s, y1], "dimensions": f"{w}x{h}",
    })
    for attempt in range(retries):
        r = requests.get(url, timeout=900)
        if r.status_code == 200:
            break
        try:
            msg = r.json()["error"]["message"]
        except Exception:
            msg = r.text[:300]
        # 429 / 500 "capacity exceeded" / 503 are transient on the free tier: back off and retry
        if r.status_code in (429, 500, 503) and attempt < retries - 1:
            time.sleep(15 * (attempt + 1))
            continue
        raise RuntimeError(f"Earth Engine download failed ({r.status_code}): {msg}")
    data = r.content
    if data[:2] == b"PK":  # zipped response
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            data = z.read([n for n in z.namelist() if n.endswith(".tif")][0])
    out.write_bytes(data)
    return out


def download_image(img: ee.Image, grid: dict, path: Path, tiles: tuple[int, int] = (6, 6),
                   nodata=None, workers: int = 3) -> Path:
    """Download `img` on `grid` as one compressed GeoTIFF (band names kept as descriptions)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    W, H = grid["width"], grid["height"]
    cols = [round(i * W / tiles[0]) for i in range(tiles[0] + 1)]
    rows = [round(j * H / tiles[1]) for j in range(tiles[1] + 1)]
    jobs = [(cols[i], rows[j], cols[i + 1] - cols[i], rows[j + 1] - rows[j])
            for i in range(tiles[0]) for j in range(tiles[1])]
    names = img.bandNames().getInfo()
    with tempfile.TemporaryDirectory() as tmp:
        parts = [Path(tmp) / f"t{k}.tif" for k in range(len(jobs))]
        with ThreadPoolExecutor(workers) as ex:
            list(ex.map(lambda a: _fetch(img, grid, *a[0], a[1]), zip(jobs, parts)))
        srcs = [rasterio.open(p) for p in parts]
        mosaic, transform = merge(srcs, nodata=nodata)
        profile = srcs[0].profile | {
            "driver": "GTiff", "height": mosaic.shape[1], "width": mosaic.shape[2],
            "transform": transform, "compress": "deflate", "predictor": 2,
            "tiled": True, "blockxsize": 512, "blockysize": 512, "nodata": nodata, "BIGTIFF": "IF_SAFER",
            "photometric": "MINISBLACK",
        }
        for s in srcs:
            s.close()
        part = path.with_name(path.name + ".part")  # write then rename, so readers never see a half file
        with rasterio.open(part, "w", **profile) as dst:
            dst.write(mosaic)
            dst.descriptions = tuple(names)
        part.replace(path)
    return path
