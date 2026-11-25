"""Write QGIS .qml styles for the output rasters/vectors.

Styles go to qgis/styles/ (tracked) and are also copied next to each output file as a sidecar
(<name>.qml), which QGIS applies automatically when the layer is added.
Run from the project root:  .venv\\Scripts\\python src\\write_qgis_styles.py
"""
import shutil
from xml.sax.saxutils import quoteattr
from pathlib import Path

import config

ROOT = config.ROOT
STYLES = ROOT / "qgis" / "styles"

HEAD = "<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>\n<qgis version=\"3.28\" styleCategories=\"Symbology\">\n"


def paletted(entries, band=1):
    rows = "\n".join(f'        <paletteEntry value="{v}" color="{c}" alpha="{a}" label={quoteattr(l)}/>' for v, c, a, l in entries)
    return (HEAD + f'  <pipe>\n    <rasterrenderer type="paletted" band="{band}" opacity="1" alphaBand="-1">\n'
            f"      <colorPalette>\n{rows}\n      </colorPalette>\n    </rasterrenderer>\n  </pipe>\n</qgis>\n")


def graduated_fill(field, classes):
    ranges, symbols = [], []
    for i, (lo, hi, color, label) in enumerate(classes):
        ranges.append(f'      <range lower="{lo}" upper="{hi}" symbol="{i}" label={quoteattr(label)} render="true"/>')
        symbols.append(
            f'      <symbol type="fill" name="{i}" alpha="1"><layer class="SimpleFill">'
            f'<Option type="Map"><Option type="QString" name="color" value="{color}"/>'
            f'<Option type="QString" name="outline_style" value="no"/></Option></layer></symbol>')
    return (HEAD + f'  <renderer-v2 type="graduatedSymbol" attr="{field}" graduatedMethod="GraduatedColor">\n'
            f"    <ranges>\n" + "\n".join(ranges) + "\n    </ranges>\n    <symbols>\n" + "\n".join(symbols)
            + "\n    </symbols>\n  </renderer-v2>\n</qgis>\n")


FLOOD = paletted([(0, "#ece9e2", 255, "not flooded"), (1, "#2171b5", 255, "flood"),
                  (2, "#08306b", 255, "permanent water"), (255, "#ffffff", 0, "not observed")])
FREQ = paletted([(0, "#ece9e2", 0, "never flooded")] +
                [(i, c, 255, f"flooded on {i} date{'s' if i > 1 else ''}") for i, c in
                 enumerate(["#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c", "#08306b"], start=1)]
                + [(255, "#ffffff", 0, "outside district")])
EXPO = paletted([(0, "#ffffff", 0, "not built-up"), (1, "#8c8c8c", 255, "built-up > 100 m from flood"),
                 (2, "#fdae61", 255, "built-up 50-100 m from flood"), (3, "#d7301f", 255, "built-up <= 50 m from flood"),
                 (255, "#ffffff", 0, "outside district")])
GRID = graduated_fill("exposed_any_km2", [
    # "0" range ends at half a 10 m pixel (0.00005 km2) so one exposed pixel (0.0001 km2) is never labelled 0
    (0, 0.00005, "#f4f2ee", "0"), (0.00005, 0.005, "#fdd49e", "< 0.5 ha"), (0.005, 0.01, "#fc8d59", "0.5-1 ha"),
    (0.01, 0.02, "#d7301f", "1-2 ha"), (0.02, 1, "#7f0000", "> 2 ha")])

STYLE_FILES = {
    "flood_classes.qml": (FLOOD, sorted(config.OUT_RASTERS.glob("flood_2022*_t*.tif"))),
    "flood_frequency.qml": (FREQ, [config.OUT_RASTERS / "flood_frequency_june2022.tif"]),
    "exposure_classes.qml": (EXPO, [config.OUT_RASTERS / "exposure_any_june2022.tif"]),
    "exposure_grid_1km.qml": (GRID, [config.DATA_PROCESSED / "exposure_grid_1km.gpkg"]),
}

if __name__ == "__main__":
    STYLES.mkdir(parents=True, exist_ok=True)
    for name, (xml, targets) in STYLE_FILES.items():
        (STYLES / name).write_text(xml, encoding="utf-8")
        for t in targets:
            if t.exists():
                shutil.copy(STYLES / name, t.with_suffix(".qml"))
        print(f"{name:24s} -> {len([t for t in targets if t.exists()])} sidecar(s)")
