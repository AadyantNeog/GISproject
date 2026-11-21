"""Download the boundary and reference flood-map datasets into data/raw/.

Run from the project root:  python src/download_data.py
Files that already exist are skipped. Zip archives are extracted next to themselves.
"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

SA = "https://sentinel-asia.org/EO/2022"

DATASETS: dict[str, str] = {
    # --- District boundaries -------------------------------------------------
    # geoBoundaries gbOpen IND ADM2 (year represented 2021, source: LGD / Pathways Data), ODbL 1.0
    "boundary/geoboundaries/geoBoundaries-IND-ADM2.geojson":
        "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM2/geoBoundaries-IND-ADM2.geojson",
    # datta07/INDIAN-SHAPEFILES (cross-check + sub-districts / revenue circles)
    "boundary/datta07/ASSAM_DISTRICTS.geojson":
        "https://raw.githubusercontent.com/datta07/INDIAN-SHAPEFILES/master/STATES/ASSAM/ASSAM_DISTRICTS.geojson",
    "boundary/datta07/ASSAM_SUBDISTRICTS.geojson":
        "https://raw.githubusercontent.com/datta07/INDIAN-SHAPEFILES/master/STATES/ASSAM/ASSAM_SUBDISTRICTS.geojson",

    # --- Reference flood maps (Sentinel Asia event pages) -----------------------
    # EOS-RS Flood Proxy Map, Sentinel-1, 21 Jun 2022
    "reference/eosrs_s1_20220621/EOS-RS_20220621_FPM_S1_India_Floods_v0.3_SHP.zip":
        f"{SA}/article20220615IN/EOS-RS_20220621_FPM_S1/EOS-RS_20220621_FPM_S1_India_Floods_v0.3_SHP.zip",
    # EOS-RS Flood Proxy Map, ALOS-2 (L-band, independent sensor), 22 Jun 2022
    "reference/eosrs_alos2_20220622/EOS-RS_20220622_FPM_A2_India_Floods_v0.4_SHP.zip":
        f"{SA}/article20220615IN/EOS-RS_20220622_FPM_A2/EOS-RS_20220622_FPM_A2_India_Floods_v0.4_SHP.zip",
    # EOS-RS Flood Proxy Map, Sentinel-1, 18 May 2022 (May flood wave -> baseline check)
    "reference/eosrs_s1_20220518/EOS-RS_20220518_FPM_S1_India_Floods_v0.4_SHP.zip":
        f"{SA}/article20220515IN/EOS-RS_20220518_FPM_S1/EOS-RS_20220518_FPM_S1_India_Floods_v0.4_SHP.zip",
    # MBRSC flood area, Sentinel-1, 15/16 Jun 2022
    "reference/mbrsc_s1_20220616/MBRSC_Flood_Area_15062022.zip":
        f"{SA}/article20220615IN/MBRSC/MBRSC_Flood_Area_15062022.zip",
    # ISRO/NRSC map products (PDF, need georeferencing for quantitative use)
    "reference/isro_alos2_20220622/floodmap_assam_22jun2022.pdf":
        f"{SA}/article20220615IN/ISRO/floodmap_assam_22jun2022.pdf",
    "reference/isro_nagaon_may2022/plate-6-nagaon-pre-post.pdf":
        f"{SA}/article20220515IN/ISRO/plate-6-nagaon-pre-post.pdf",
}


def fetch(rel: str, url: str) -> None:
    dest = RAW / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"skip  {rel}")
    else:
        print(f"get   {rel}")
        req = urllib.request.Request(url, headers={"User-Agent": "gis-coursework-downloader"})
        with urllib.request.urlopen(req, timeout=600) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    if dest.suffix == ".zip":
        with zipfile.ZipFile(dest) as z:
            for m in z.infolist():
                name = Path(m.filename).name
                if m.is_dir() or m.filename.startswith("__MACOSX") or not name:
                    continue
                target = dest.parent / name
                if not target.exists():
                    target.write_bytes(z.read(m))


if __name__ == "__main__":
    only = set(sys.argv[1:])
    for rel, url in DATASETS.items():
        if not only or any(k in rel for k in only):
            fetch(rel, url)
