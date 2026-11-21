"""Project-wide settings. Edit EE_PROJECT before running the notebooks."""
from pathlib import Path

# Google Cloud project registered for Earth Engine (shown in the Cloud console project picker).
EE_PROJECT = "gis-project-515401"

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_FIGURES = ROOT / "outputs" / "figures"
OUT_RASTERS = ROOT / "outputs" / "rasters"

DISTRICT_NAME = "Nagaon"
BOUNDARY_FILE = DATA_PROCESSED / "nagaon_2022.geojson"

# Equal-area-ish metric CRS for area statistics (UTM 46N covers 90-96 E).
CRS_METRIC = "EPSG:32646"

# Analysis window
BASELINE_DRY = ("2022-01-01", "2022-04-15")   # dry-season reference stack
EVENT_WINDOW = ("2022-06-01", "2022-07-05")   # June 2022 event
INVENTORY_WINDOW = ("2022-01-01", "2022-07-31")

# Sentinel-1A tracks used (from notebooks/01_inventory). Dates are UTC acquisition dates.
#   77 DESCENDING  ~23:47 UTC (05:17 IST next day), 100 % of district
#   41 ASCENDING   ~12:30 UTC (18:00 IST same day),  93 % of district
TRACKS = {77: "DESCENDING", 41: "ASCENDING"}
EVENT_DATES = [  # (UTC date, relative orbit), chronological
    ("2022-06-04", 41),
    ("2022-06-06", 77),
    ("2022-06-16", 41),
    ("2022-06-18", 77),
    ("2022-06-28", 41),
    ("2022-06-30", 77),
]

# Default detection parameters (varied in the sensitivity notebook)
DEFAULT_PARAMS = {
    "diff_db": -3.0,      # event VH minus dry baseline VH must be below this
    "vh_db": "otsu",      # absolute VH water threshold: number (dB) or "otsu" (automatic, per scene)
    "vh_fallback_db": -20.0,  # used if Otsu fails or is implausible
    "hand_m": 15.0,       # HAND exclusion (Twele et al. 2016)
    "slope_deg": 5.0,     # slope exclusion
    "perm_months": 10,    # JRC seasonality >= this many months -> permanent water
    "mmu_px": 8,          # minimum connected flood pixels (10 m) to keep
}
