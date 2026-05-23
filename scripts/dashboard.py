"""
dashboard.py  —  IUD-NEPS Step 7: Dashboard
============================================
Generates outputs/dashboard.html and opens it in your browser.

Run from project root:
    py -3.12 scripts/dashboard.py
"""

import os
import sys
import logging
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C
from dashboard.data_prep      import load_all, prepare_stats, prepare_shap, prepare_scenarios
from dashboard.geojson_builder import build_geojson
from dashboard.html_generator  import build_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(C.BASE_DIR, "dashboard.log"), mode="w"),
    ]
)
log = logging.getLogger("iud-neps")

if __name__ == "__main__":
    log.info("=" * 55)
    log.info("IUD-NEPS  --  Step 7: Dashboard")
    log.info("=" * 55)

    log.info("--- [1/4] Loading data ---")
    df, df_shap, df_prop = load_all(log)

    log.info("--- [2/4] Preparing data ---")
    stats    = prepare_stats(df)
    shap     = prepare_shap(df_shap)
    scenarios= prepare_scenarios(df)

    log.info("--- [3/4] Building GeoJSON ---")
    geojson  = build_geojson(df, log)

    log.info("--- [4/4] Generating HTML ---")
    html     = build_html(geojson, shap, scenarios, stats)

    with open(C.PATHS["dashboard"], "w", encoding="utf-8") as f:
        f.write(html)

    size_mb = os.path.getsize(C.PATHS["dashboard"]) / 1e6
    log.info(f"Dashboard saved: {size_mb:.1f} MB -> {C.PATHS['dashboard']}")
    log.info("Opening in browser ...")
    webbrowser.open(f"file:///{C.PATHS['dashboard'].replace(os.sep, '/')}")

    log.info("=" * 55)
    log.info("Done.")
    log.info("=" * 55)