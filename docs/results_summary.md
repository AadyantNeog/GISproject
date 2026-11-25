# Flood inundation and settlement exposure in Nagaon, June 2022 — results summary

Working notes for the report. All numbers come from the tables in `outputs/tables/` and are
reproducible with notebooks 01–06. Figures referenced are in `outputs/figures/`.

## 1. Data and study area

* **District boundary:** Nagaon as constituted in June 2022 (Hojai separate; it was re-merged only on
  31 Dec 2022). Source: datta07/INDIAN-SHAPEFILES, 2,577.6 km² geodesic (2,575.6 km² on the 10 m grid).
  This matches the study area of Irukumati et al. (2025) exactly. geoBoundaries 2021 (LGD) gives 2,508 km²
  and is kept as a cross-check. Seven 2011-census sub-districts fall inside the 2022 district:
  Kaliabor, Samaguri, Rupahi, Dhing, Nagaon, Raha, Kampur.
* **SAR:** Sentinel-1A IW GRD, VV+VH (Sentinel-1B had failed in Dec 2021, so 12-day repeat per track).
  Three tracks cover the district (`s1_inventory_by_track.csv`); two were used:
  * track 77 descending (100 % coverage): 6, 18, 30 June (23:47 UTC = 05:17 IST the next morning);
  * track 41 ascending (93 % coverage, misses the eastern tip of Kaliabor): 4, 16, 28 June (~18:00 IST).
  * Baseline: median of the Jan–mid-Apr 2022 scenes of the same track (8 for track 77, 8 for track 41; 16 in total).
    A May baseline was avoided because Nagaon flooded in mid-May 2022 (EOS-RS 18 May map: 94.6 km² in the district).
* **Ancillary data:** MERIT Hydro HAND and DEM slope (90 m), JRC Global Surface Water v1.4 (to 2021),
  ESA WorldCover 2021 v200 (built-up = class 50; 63.9 km², 2.5 % of the district).
* **References:** MBRSC flood map (Sentinel-1, 16 June), EOS-RS Flood Proxy Map (ALOS-2 L-band, 22 June),
  EOS-RS (Sentinel-1, 18 May), all from Sentinel Asia; NRSC/ISRO 22 June map (PDF only); published areas in
  Irukumati et al. (2025), including the NRSC reference areas they cite.

## 2. Method (short)

1. **Preprocessing (Google Earth Engine):** GRD σ⁰ (already calibrated and terrain-corrected in GEE), border-noise
   mask, Lee speckle filter (7×7, ENL 4.4, linear power), same-track dry-season median baseline. Stacks downloaded on a
   fixed 10 m UTM 46N grid.
2. **Change detection (Python):** flood where VH(event) − VH(baseline) < −3 dB **and** VH(event) < T, with T from an
   edge-based Otsu split (Donchyts et al. 2016) per scene — −19.1 to −20.7 dB on all six dates, inside the usual
   open-water range, so the fallback (−20 dB) was never needed.
3. **Exclusions:** HAND ≥ 15 m (Twele et al. 2016), slope ≥ 5° (MERIT DEM; SRTM slope was rejected because canopy and
   building noise made > 10 % of the lowest land exceed 5°), JRC permanent water (seasonality ≥ 10 months; in GSW v1.4 this band counts the months with water in 2021 only),
   patches < 8 pixels.
4. **Exposure:** WorldCover built-up within 30 / 50 / 100 m of mapped flood water (50 m main). Direct overlap is not
   meaningful: SAR cannot see water among buildings, so the flood mask almost never falls on built-up pixels
   (0.14 km² across all dates).

## 3. Results by research question

### (i) How did inundation vary between June acquisition dates?

| Date (UTC) | Track | Flooded km² | In common footprint km² |
|---|---|---|---|
| 4 Jun | 41 A | 142.8 | 139.8 |
| 6 Jun | 77 D | 124.4 | 116.0 |
| 16 Jun | 41 A | 303.1 | 298.6 |
| 18 Jun | 77 D | 503.4 | 468.4 |
| 28 Jun | 41 A | 559.0 | 555.5 |
| 30 Jun | 77 D | 600.1 | 560.4 |

* Flooding was modest in early June (~120–145 km², ~5 % of the district), rose sharply between 6 and 18 June,
  and was still expanding or persisting at the end of the month (≈ 560 km² in the common footprint on 28–30 June).
  Both tracks show the same trajectory, which supports the result not being a track artefact.
* 766 km² (30 % of the district) was flooded on at least one date; 405 km² on three or more dates
  (`map_flood_frequency.png`). Persistent flooding is concentrated in Raha, Kampur and the southern part of
  Nagaon sub-district (Kopili/Kolong lowlands).
* By sub-district (`flood_area_by_subdistrict.csv`), Kampur peaked on 18 June (171 km²) while Raha and Nagaon peaked
  on 28–30 June (167 and 117 km²), so the location of the worst flooding changed during the month.

### (ii) Where did inundation overlap built-up land?

| Scenario | ≤ 30 m | ≤ 50 m | ≤ 100 m | Built-up clusters ≤ 50 m |
|---|---|---|---|---|
| 18 Jun | 1.2 km² | 3.6 km² (5.6 %) | 12.2 km² | 4,726 |
| 30 Jun | 1.4 km² | 4.6 km² (7.2 %) | 17.2 km² (26.8 %) | 6,248 |
| Any June date | 2.6 km² | **7.2 km² (11.3 %)** | 22.3 km² (34.9 %) | 8,806 of 29,799 |

* Largest absolute exposure: Nagaon sub-district (1.64 km², town area). Highest share of built-up exposed: **Raha (25 %)**
  and **Kampur (23 %)** (`exposure_by_subdistrict.csv`, `map_exposure.png`).
* The pixel zoom near Raha shows much of the "exposed" built-up class is **roads and linear settlements along roads**
  bordering flooded fields — WorldCover's built-up class includes roads. Exposure therefore mixes settlement and
  transport infrastructure.
* Exposure is spatial proximity, not confirmed damage or affected population.

### (iii) How sensitive are extent and exposure to detection thresholds?

One-at-a-time sweeps on 16, 18 and 30 June (`sensitivity_*.csv`, `sensitivity_*.png`):

| Setting varied | Range tested | Flood area range (% of default) | Comment |
|---|---|---|---|
| VH drop threshold | −1 to −6 dB | 43–73 % | most influential; 18 Jun: 358–574 km² |
| Absolute VH threshold | −17 to −24 dB (plus each date's exact Otsu value as default) | 32–36 % | 18 Jun: 373–534 km² |
| Permanent-water definition | JRC 2021 seasonality ≥ 1 … 12 months / none | 16–19 % | excluding any pixel wet in 2021 removes ~92 km² on 18 Jun; 161.8 km² more lies on land wet in earlier years only, which this test does not exclude |
| Minimum patch size | 1–100 px | 6–11 % | exposure is more sensitive (2.5–4.5 km² on 18 Jun) |
| Polarisation | VH vs VV | 7–10 % | VV (Otsu −13.1 dB) maps ~10 % less |
| HAND / slope exclusions | 5 m–off / 2°–off | < 1 % | the district is a flat floodplain |

* Over commonly used thresholds (drop −2 to −4 dB, VH −19 to −22 dB) the 18 June area is **423–575 km²**
  (default 503; −16 % / +14 %).
* Exposure within 50 m scales roughly with flood area but is more sensitive in relative terms
  (18 Jun: 1.6–4.8 km² across the drop sweep).
* F1 against the references barely changes across settings (MBRSC 0.41–0.48; ALOS-2 0.16–0.25), so the
  references cannot by themselves pin down a "best" threshold.

## 4. Agreement with reference maps and published estimates

Pixel agreement (`validation_pixel.csv`):

| Reference | Our map | Ref km² | Ours km² | Precision | Recall | F1 | OA | κ |
|---|---|---|---|---|---|---|---|---|
| MBRSC S1, 16 Jun | 16 Jun t41 (same scene) | 128.1 | 303.1 | 0.33 | 0.78 | 0.46 | 0.90 | 0.42 |
| EOS-RS ALOS-2, 22 Jun | 18 Jun t77 | 143.7 | 503.4 | 0.14 | 0.51 | 0.22 | 0.81 | 0.15 |
| EOS-RS ALOS-2, 22 Jun | 28 Jun t41 | 135.0 | 559.0 | 0.12 | 0.50 | 0.20 | 0.77 | 0.12 |

* **Coverage assumption:** the reference layers hold only flood polygons, not the footprint each product assessed, so
  everything outside the polygons is scored as dry. Precision, F1, OA and κ therefore assume each product covered the
  whole district (recall does not). MBRSC's polygons stop at 93.26°E, short of the district's eastern edge (93.32°E).

* The rapid-mapping proxies are much smaller than our maps (and than NRSC's own areas below), so low precision
  largely reflects conservative references. Agreement improves at coarser scales
  (16 Jun vs MBRSC: r = 0.57 at 100 m → 0.61 at 1 km; 18 Jun vs ALOS-2: 0.28 → 0.57; `validation_cells.csv`).
* **Ours only** (commission) is mostly cropland (378 of 431 km² on 18 Jun), ~46 % of it in places JRC has seen water
  before — consistent with flooded/waterlogged paddy and seasonal wetlands that a dry-season baseline cannot separate
  from event flooding.
* **Reference only** (omission) vs ALOS-2: 36 of 71 km² is **tree cover**. That is consistent with L-band seeing
  water beneath canopy where C-band cannot, but the comparison cannot isolate the cause: flooding may have changed in
  the four days between scenes, and the products use different methods.
* Sub-district rankings agree well (Spearman ρ = 0.82 vs MBRSC, 0.86 / 0.71 vs ALOS-2).

Published areas for the same district and dates (`validation_published_areas.csv`):

| Source | 18 Jun km² | 30 Jun km² |
|---|---|---|
| NRSC reference (as cited by Irukumati et al.) | 413.3 | 597.3 |
| Irukumati et al., Random Forest (VV / VH / VV+VH) | 395.6* / 383.2 / 400.3 | 565.3 / 583.2 / 592.1 |
| Irukumati et al., K-means (VV / VH / VV+VH) | 413.3 / 389.2 / 401.8 | 613.2 / 592.6 / 551.9 |
| **This study** | **503.4** | **600.1** |

\* the paper gives 395.56 km² in its text (p. 11) but 295.56 km² in Table 3 (p. 13); the text value is used.
The NRSC 30 June value (597.32 km²) is confirmed in the paper's discussion text; our 600.1 km² differs by 0.47 %.
On 18 June we are ~22 % higher than NRSC. NRSC's 413.3 km² lies 9.9 km² below the common-threshold range
(423.2–574.6 km², joint sweep) but inside the wider one-at-a-time VH-drop sweep (358–574 km²; a −5 dB drop gives 411 km²).

**May wave:** 15 % of the 18 May flood area was flooded again on 4–6 June, rising to 50–57 % on 18–30 June
(`validation_may_overlap.csv`); the January–April baseline keeps May water out of the reference image.

## 5. Limitations (for the discussion)

* C-band likely misses flooding under tree canopy (rural Assamese villages are largely under homestead trees, which
  WorldCover classes as tree cover) and cannot see water among buildings (double bounce). Exposure is therefore a
  lower-bound proximity measure.
* Agreement scores assume each reference product assessed the whole district (footprints unknown).
* The permanent-water mask and its sensitivity test use JRC's 2021 seasonality, not the full 1984–2021 record.
* Late-June increases may include deliberately flooded / waterlogged paddy fields (sali transplanting season); the
  dry-season baseline cannot separate these from flood water.
* Track 41 does not cover the eastern tip of Kaliabor; use the common-footprint column for cross-track comparisons.
* References are themselves rapid-mapping products with unknown accuracy and different dates (22 Jun ALOS-2 lies between
  our 18 and 28 June scenes). NRSC/ASDMA GIS layers were not publicly available; only PDF maps.
* WorldCover built-up includes roads; settlement clusters are 8-connected built-up patches, not villages.
* 2011-census sub-districts are used as reporting units; they are not identical to current revenue circles.

## 6. Output index

| Item | File |
|---|---|
| Flood maps per date (0 dry, 1 flood, 2 permanent water, 255 no data) | `outputs/rasters/flood_YYYYMMDD_tNN.tif` |
| Flood frequency (band 1 dates flooded, band 2 dates observed) | `outputs/rasters/flood_frequency_june2022.tif` |
| Exposure classes (any date) | `outputs/rasters/exposure_any_june2022.tif` |
| 1 km exposure grid | `data/processed/exposure_grid_1km.gpkg` |
| Reference layers clipped to Nagaon | `data/processed/reference_nagaon.gpkg` |
| QGIS styles (auto-applied sidecars) | `qgis/styles/*.qml` |
| Report maps | `outputs/figures/map_*.png` |
| Charts | `outputs/figures/flood_*`, `exposure_*`, `sensitivity_*`, `validation_*` |

## References

* Twele, A., Cao, W., Plank, S. and Martinis, S. (2016). Sentinel-1-based flood mapping: a fully automated processing chain. *IJRS* 37(13), 2990–3004.
* Irukumati, S., Vittal, A. R. and Gurunarayan, S. L. (2025). Comparative analysis of classification techniques for flood mapping using Sentinel 1 SAR data. *Environmental Earth Sciences* 84, 398.
* Donchyts, G., Schellekens, J., Winsemius, H., Eisemann, E. and van de Giesen, N. (2016). A 30 m resolution surface water mask including estimation of positional and thematic differences using Landsat 8, SRTM and OpenStreetMap. *Remote Sensing* 8(5), 386 (Canny-edge + Otsu thresholding).
* Lee, J.-S. (1980). Digital image enhancement and noise filtering by use of local statistics. *IEEE TPAMI* 2(2), 165–168.
* Pekel, J.-F. et al. (2016). High-resolution mapping of global surface water and its long-term changes. *Nature* 540, 418–422 (JRC GSW).
* Yamazaki, D. et al. (2019). MERIT Hydro: a high-resolution global hydrography map. *Water Resources Research* 55, 5053–5073.
* Zanaga, D. et al. (2022). ESA WorldCover 10 m 2021 v200.
