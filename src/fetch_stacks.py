"""Download the analysis-ready stacks from Earth Engine to outputs/rasters/stacks/.

  s1_YYYYMMDD_tNN.tif : int16 dB*100 bands VV, VH (event) and VV0, VH0 (dry baseline, same track)
  static.tif          : int16 bands hand_dm, slope_ddeg, jrc_seasonality, jrc_occurrence, worldcover

All files share the grid in data/processed/grid.json (10 m, EPSG:32646). Existing files are skipped.
Run from the project root:  .venv\\Scripts\\python -u src\\fetch_stacks.py
"""
import json
import time

import config
import download as dl
import ee_utils
import floodmap as fm

STACK_DIR = config.OUT_RASTERS / "stacks"
GRID_FILE = config.DATA_PROCESSED / "grid.json"


def main():
    ee_utils.init()
    aoi = ee_utils.district_geometry()
    if GRID_FILE.exists():
        grid = json.loads(GRID_FILE.read_text())
    else:
        grid = dl.grid_for(aoi)
        GRID_FILE.write_text(json.dumps(grid, indent=1))
    jobs = [("static", None)] + [(f"s1_{d.replace('-', '')}_t{o}", (d, o)) for d, o in config.EVENT_DATES]
    for name, spec in jobs:
        out = STACK_DIR / f"{name}.tif"
        if out.exists():
            print(f"skip  {name}", flush=True)
            continue
        t0 = time.time()
        img = fm.static_stack() if spec is None else fm.s1_stack(aoi, *spec)
        dl.download_image(img, grid, out, nodata=fm.NODATA)
        print(f"got   {name}  {out.stat().st_size / 1e6:.0f} MB  {time.time() - t0:.0f}s", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
