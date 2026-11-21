"""Project-wide settings. Edit EE_PROJECT before running the notebooks."""
from pathlib import Path

# Google Cloud project registered for Earth Engine (shown in the Cloud console project picker).
EE_PROJECT = "YOUR-CLOUD-PROJECT-ID"

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
