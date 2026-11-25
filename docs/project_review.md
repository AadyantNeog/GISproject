# Nagaon flood mapping project review

Reviewed on 21 November 2026 at commit `a090af5`. All six June flood maps reproduced pixel for pixel from the saved Sentinel-1 and ancillary stacks. The increase in mapped flooding through June appears on both tracks within their common footprint. The main corrections concern what the reference maps establish, which water history the sensitivity test used, and how the report compares its results with published estimates.

## Verified results

| Quantity | Recomputed from the local rasters |
|---|---:|
| Mapped flood on 18 June | 503.3880 km² |
| Mapped flood on 30 June | 600.1301 km² |
| Flooded on at least one of the six dates | 766.4239 km² |
| Flooded on at least three dates | 405.3868 km² |
| Footprint observed on all six dates | 2,389.8706 km² |
| Built-up land within 50 m of mapped flood on any June date | 7.2364 km² |

The daily areas and common-footprint totals agree with the saved tables at their published precision. The flood-frequency and observation-count bands agree with the six individual maps. The 50 m exposure result measures proximity to mapped water and includes built-up infrastructure such as roads. [Daily flood areas](../outputs/tables/flood_area_by_date.csv) · [Exposure by date](../outputs/tables/exposure_by_date.csv)

## Findings affecting the report

### 1. Reference-map coverage is assumed in the agreement scores

The validation notebook rasterizes the supplied flood polygons with zero everywhere else. It scores every pixel observed by the project's Sentinel-1 map in the district. There is no separate mask identifying where the reference product could detect flooding. If a reference product covers only part of the scoring area, a project detection outside that coverage counts as a false positive, and a dry project pixel there counts as a true negative.

The reported F1 scores reproduce under that assumption: 0.464 for the 16 June MBRSC comparison, 0.224 for the 18 June map against ALOS-2, and 0.196 for the 28 June map against ALOS-2. The unresolved question is how much of the scoring area each reference product assessed. Verify the reference footprints before interpreting precision, F1, or overall accuracy as district-wide performance. If the footprints cannot be recovered, state the assumption alongside the scores. [Notebook generator, line 458](../src/make_notebooks.py#L458) · [Agreement calculation, line 142](../src/classify.py#L142) · [Validation table](../outputs/tables/validation_pixel.csv) · [Sentinel Asia product listing](https://sentinel-asia.org/EO/2022/article20220615IN.html)

### 2. The ALOS-2 comparison cannot isolate the effect of canopy

Of the 71.2 km² mapped only by the 22 June ALOS-2 product when compared with the 18 June Sentinel-1 map, 36.0 km² falls in the WorldCover tree-cover class. That supports canopy as a plausible explanation. Flooding could also have changed in the intervening four days, and the products use different detection methods. The report states that the comparison shows water beneath trees was missed. The evidence establishes where the products disagreed and leaves the cause open. [Land-cover breakdown](../outputs/tables/validation_disagreement_landcover.csv) · [Report abstract, line 75](report/report.tex#L75) · [Report interpretation, line 520](report/report.tex#L520)

### 3. The strictest water mask tests 2021 seasonality

The report attributes an approximately 90 km² reduction on 18 June to excluding every pixel JRC had ever observed as wet. The sweep actually sets the minimum to one wet month in the JRC v1.4 **2021 seasonality** band. On the default 18 June map, **161.8198 km²** of flooded pixels had positive historical water occurrence and zero 2021 seasonality. A one-month threshold leaves those pixels eligible. Describe the existing test as a 2021 water exclusion. A claim about any historical detection would require a separate test using JRC's maximum water extent band. [Mask implementation, line 130](../src/classify.py#L130) · [Report claim, line 447](report/report.tex#L447) · [JRC v1.4 user guide](https://storage.googleapis.com/global-surface-water/downloads_ancillary/DataUsersGuidev2021.pdf)

### 4. The 18 June NRSC figure lies outside the stated common-threshold range

Filtering the joint sweep to a VH drop of −4 to −2 dB and an absolute VH threshold of −22 to −19 dB gives **423.2034–574.6460 km²**. The published NRSC estimate of **413.28 km²** lies **9.92 km² below** that minimum. The wider one-at-a-time drop sweep spans the NRSC value. The report should identify which sweep supports its comparison. For 30 June, the paper confirms the NRSC figure of 597.32 km². The project's 600.1301 km² differs by **0.47%** in total area. [Joint sweep](../outputs/tables/sensitivity_joint_18jun.csv) · [One-at-a-time sweep](../outputs/tables/sensitivity_one_at_a_time.csv) · [Report comparison, line 540](report/report.tex#L540) · [Results summary](results_summary.md)

### 5. The inventory contains 16 baseline scenes across the selected tracks

Filtering the scene inventory to the configured window, 1 January inclusive through 15 April exclusive, gives **eight scenes on track 41 and eight on track 77**. The report and results summary give nine for track 41, bringing the reported total to 17. Correct the baseline count in the methods and acquisition table. The June event-date list agrees with the inventory for the two selected tracks. [Configuration, line 21](../src/config.py#L21) · [Scene inventory](../outputs/tables/s1_inventory.csv) · [Report dataset table, line 152](report/report.tex#L152) · [Report acquisition table, line 180](report/report.tex#L180)

### 6. The cited paper gives two values for the same Random Forest result

For the 18 June VV Random Forest estimate, Irukumati et al. give **395.56 km²** in the prose on page 11 and **295.56 km²** in Table 3 on page 13. The project uses the prose value. Flag the discrepancy where the published comparison is presented and identify the source of the chosen figure. The discrepancy concerns Random Forest only. Table 3 gives the NRSC results separately. [Paper](https://doi.org/10.1007/s12665-025-12381-3) · [Transcribed values, line 545](../src/make_notebooks.py#L545) · [Published-area comparison](../outputs/tables/validation_published_areas.csv)

## Implementation findings

| Finding | Evidence and effect |
|---|---|
| The 1 km exposure grid drops partial edge cells. | The 9,277 × 8,232 raster is trimmed to complete 100 × 100 pixel blocks. The omitted eastern and southern strips contain **0.5655 km² of district land**, including **0.0637 km²** of the flood union. The grid sums to 766.3602 km² of flooding. The strips contain zero built-up area within 50 m of mapped flooding, so the headline exposure total still reconciles. [Grid aggregation, line 250](../src/make_notebooks.py#L250) |
| The QGIS style labels some positive exposure as zero. | The first graduated range, labelled “0”, includes 0.0001 km², the area of one 10 m pixel. **97 cells** have exactly that value. QGIS uses the first matching range at a shared endpoint. The underlying GeoPackage retains the correct values. [Style definition, line 48](../src/write_qgis_styles.py#L48) · [QGIS range selection](https://api.qgis.org/api/qgsgraduatedsymbolrenderer_8cpp_source.html) |
| The absolute-VH sweep marks a nearby threshold as the default. | The sweep accepts any threshold within 0.5 dB of the actual Otsu value. On 30 June the starred −20 dB setting gives **596.9639 km²**. The actual Otsu threshold of −19.8614 dB gives **600.1301 km²**. The summary also uses the starred row as its denominator. [Default flag, line 355](../src/make_notebooks.py#L355) · [Summary denominator, line 431](../src/make_notebooks.py#L431) |
| The Otsu fallback fails on an empty edge sample. | A uniform −20 dB scene with a valid observation mask produces no edges. The call to `threshold_otsu` raises `IndexError` before the configured fallback can run. All six saved scenes produced valid thresholds. [Threshold calculation, line 92](../src/classify.py#L92) |
| A flood-free map can produce positive exposure. | A 10 × 10 test raster with all pixels dry and built-up returned **0.002 km²** exposed within 50 m. The distance transform receives an array with no flood pixels. The exposure notebook repeats the same calculation. An explicit empty-flood case should return zero exposure. Each June map contains flood pixels. [Exposure helper, line 164](../src/classify.py#L164) · [Notebook calculation, line 201](../src/make_notebooks.py#L201) |

## Verification scope

The review covered the proposal, report and cited local papers, Python sources, all six notebooks, output tables and figures, GIS layers, and QGIS styles. Local checks used the existing project environment and saved data. They included recomputing each Otsu threshold and classified map in memory, recounting flood and exposure areas, and reproducing pixel agreement from the clipped reference polygons. All six notebook sources match their generator, and each output style sidecar matches its tracked QGIS style.

Fresh Earth Engine exports and remote downloads were outside the verification run. Pixel agreement between regenerated and saved local outputs establishes computational reproducibility from those inputs. Independent observations of on-the-ground inundation would be needed to establish flood-detection accuracy.
