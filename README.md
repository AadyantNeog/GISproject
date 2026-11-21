# Flood Inundation and Settlement Exposure — Nagaon, Assam, June 2022

Sentinel-1 SAR change detection in Google Earth Engine (Python API) to map June 2022 flood
inundation in Nagaon district, separate it from permanent water, and estimate overlap with
built-up land (ESA WorldCover 2021). Group: Aadyant Neog (BT2024186), Jeswin Jose (BT2024142).

## Layout

```
notebooks/   01_inventory … 06_validation (run in order)
src/         shared functions (floodmap.py) and download_data.py
data/raw/    downloaded boundaries + reference flood maps (git-ignored; re-create with the script)
outputs/     tables/ and figures/ (tracked), rasters/ (git-ignored GeoTIFFs)
qgis/        QGIS project and print layouts
docs/        proposal and notes
```

## Setup (Windows)

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python src\download_data.py
.venv\Scripts\earthengine authenticate      # one-time, opens a browser sign-in
```

Then set your Google Cloud project ID (the one registered for Earth Engine) in `src/config.py`
and open the notebooks with the "Python (GISproject)" kernel.

## Data sources

| Dataset | Use | Source |
|---|---|---|
| Sentinel-1 GRD (`COPERNICUS/S1_GRD`) | flood detection | ESA / Copernicus via GEE |
| JRC Global Surface Water v1.4 | permanent water mask | EC JRC via GEE |
| MERIT Hydro HAND, SRTM 30 m | terrain / false-positive masks | via GEE |
| ESA WorldCover 2021 v200 | built-up class (50) | ESA via GEE |
| geoBoundaries IND ADM2 (2021, LGD) | district boundary (Hojai separate, valid for June 2022) | geoboundaries.org, ODbL |
| EOS-RS Flood Proxy Map, ALOS-2 L-band, 22 Jun 2022 | reference (144.1 km² in Nagaon) | Sentinel Asia |
| MBRSC flood area, Sentinel-1, 16 Jun 2022 | reference (128.2 km² in Nagaon) | Sentinel Asia |
| EOS-RS Flood Proxy Map, Sentinel-1, 18 May 2022 | May-wave check for the baseline (94.5 km²) | Sentinel Asia |
| EOS-RS Flood Proxy Map, Sentinel-1, 21 Jun 2022 | does **not** cover Nagaon (kept for completeness) | Sentinel Asia |
| ISRO/NRSC flood map 22 Jun 2022 (ALOS-2, PDF) | visual reference, lists Nagaon among 17 districts | Sentinel Asia / NRSC |

District boundary: `data/processed/nagaon_2022.geojson` (datta07, 2,577.6 km², Hojai excluded —
matches the Irukumati et al. 2025 study area). geoBoundaries 2021 (2,508 km²) kept as a cross-check.
Reference layers clipped to Nagaon: `data/processed/reference_nagaon.gpkg` (`python src/clip_reference.py`).
