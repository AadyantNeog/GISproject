# Flood Inundation and Settlement Exposure — Nagaon, Assam, June 2022

Sentinel-1 SAR change detection (Google Earth Engine + Python) mapping June 2022 flood inundation in
Nagaon district, separating it from permanent water, and estimating how much built-up land
(ESA WorldCover 2021) lay close to the flood water. Group: Aadyant Neog (BT2024186), Jeswin Jose (BT2024142).

**Results write-up:** [docs/results_summary.md](docs/results_summary.md) — answers the three research
questions, validation, limitations and an index of every output.

## Headline numbers

* Flooded area: 124–143 km² on 4–6 June → 503 km² on 18 June → 600 km² on 30 June; 766 km² flooded on at least one date.
* Built-up land within 50 m of flood water: 7.2 km² (11 % of the district's built-up) on any June date; highest shares in Raha (25 %) and Kampur (23 %).
* Threshold sensitivity: 18 June area 423–575 km² over common threshold choices; the VH-drop threshold matters most.
* Agreement: 30 June area within 1 % of the NRSC figure; recall 0.78 vs the MBRSC map from the same scene; half of the flooding seen only by L-band ALOS-2 is under trees, consistent with C-band missing water beneath canopy.

## Layout

```
notebooks/  01_inventory  02_flood_detection  03_exposure  04_sensitivity  05_validation  06_maps
src/        config.py (settings) · floodmap.py (Earth Engine preprocessing) · fetch_stacks.py / download.py
            classify.py (local classification + metrics) · download_data.py · prepare_boundary.py · clip_reference.py
            make_notebooks.py (generates the notebooks) · write_qgis_styles.py
data/       raw/ downloads, processed/ boundary, reference layers, grid, exposure grid  (git-ignored)
outputs/    tables/ and figures/ (tracked) · rasters/ GeoTIFFs (git-ignored, ~2 GB with stacks)
qgis/       styles/*.qml (also copied next to each output as auto-loading sidecars)
docs/       proposal and results summary
```

## Reproduce (Windows)

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\earthengine authenticate          # one-time browser sign-in
```

Set `EE_PROJECT` in `src/config.py` to a Google Cloud project registered for Earth Engine, then:

```bash
.venv\Scripts\python src\download_data.py       # boundaries + reference flood maps
.venv\Scripts\python src\prepare_boundary.py    # June-2022 Nagaon boundary + sub-districts
.venv\Scripts\python -u src\clip_reference.py   # clip references to Nagaon
.venv\Scripts\python -u src\fetch_stacks.py     # Earth Engine preprocessing -> local stacks (~1 h, free tier)
```

Run notebooks 01–06 in order with the "Python (GISproject)" kernel (01 needs Earth Engine; 02–06 run
locally on the stacks), then `.venv\Scripts\python src\write_qgis_styles.py` for QGIS styling.

## Method in one paragraph

Sentinel-1A IW GRD scenes from descending track 77 (6, 18, 30 June) and ascending track 41 (4, 16, 28 June)
are border-masked and Lee-filtered in Earth Engine and compared with a same-track dry-season (Jan–mid-Apr 2022)
median. A pixel is flooded when VH dropped by more than 3 dB and is below a per-scene edge-based Otsu
threshold (−19.1 to −20.7 dB), outside HAND ≥ 15 m, slope ≥ 5° (MERIT), JRC permanent water and patches
< 8 px. Exposure is WorldCover built-up within 30/50/100 m of flood water, because SAR cannot detect water
among buildings.

## Data sources

| Dataset | Use | Source |
|---|---|---|
| Sentinel-1 GRD (`COPERNICUS/S1_GRD`) | flood detection | ESA / Copernicus via GEE |
| JRC Global Surface Water v1.4 | permanent / historical water | EC JRC via GEE |
| MERIT Hydro (HAND, DEM slope) | terrain exclusions | via GEE |
| ESA WorldCover 2021 v200 | built-up class (50) | ESA via GEE |
| datta07/INDIAN-SHAPEFILES (Assam districts, sub-districts) | 2022 district boundary, reporting units | GitHub |
| geoBoundaries IND ADM2 (2021, LGD) | boundary cross-check | geoboundaries.org, ODbL |
| EOS-RS Flood Proxy Map, ALOS-2 L-band, 22 Jun 2022 | reference (144 km² in Nagaon) | Sentinel Asia |
| MBRSC flood area, Sentinel-1, 16 Jun 2022 | reference (128 km² in Nagaon) | Sentinel Asia |
| EOS-RS Flood Proxy Map, Sentinel-1, 18 May 2022 | May flood wave / baseline check (95 km²) | Sentinel Asia |
| EOS-RS Flood Proxy Map, Sentinel-1, 21 Jun 2022 | does **not** cover Nagaon | Sentinel Asia |
| ISRO/NRSC flood map 22 Jun 2022 (ALOS-2, PDF) | visual reference | Sentinel Asia / NRSC |
| Irukumati et al. (2025), Table 3 | published areas incl. NRSC reference | Environmental Earth Sciences 84:398 |
