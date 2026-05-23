"""
simulate.py  —  IUD-NEPS Step 6: Scenario Simulation
=====================================================
Simulates growth impact of 4 infrastructure scenarios:
  1. Magenta Line Extension (Janakpuri West -> KMP Expressway)
  2. Jewar International Airport Opening
  3. Delhi-Gurugram RRTS Corridor
  4. Grey Line Extension (Dwarka Sec 21 -> Najafgarh)

Impact model:
  - 3-zone distance decay (walk catchment, feeder, regional)
  - Commercial intensity multiplier (dense areas benefit more)
  - 30% spillover to Queen-contiguous neighbours
  - RRTS gets wider influence zones than metro (higher speed)
  - Airport gets largest regional signal zone

Run from project root:
    py -3.12 scripts/simulate.py
"""

import os
import sys
import logging
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import pickle
from scipy.spatial import cKDTree
from shapely.geometry import Point

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(C.BASE_DIR, "simulate.log"), mode="w"),
    ]
)
log = logging.getLogger("iud-neps")


# ══════════════════════════════════════════════════════════════════════════════
# INFLUENCE ZONES BY SCENARIO TYPE
# ══════════════════════════════════════════════════════════════════════════════
ZONES_BY_TYPE = {
    "metro": [
        {"max_dist_m": 800,  "base_boost": 0.25},
        {"max_dist_m": 2000, "base_boost": 0.12},
        {"max_dist_m": 4000, "base_boost": 0.04},
    ],
    "rrts": [
        # RRTS has wider influence — higher speed, longer commute range
        {"max_dist_m": 1200, "base_boost": 0.30},
        {"max_dist_m": 4000, "base_boost": 0.15},
        {"max_dist_m": 8000, "base_boost": 0.06},
    ],
    "airport": [
        # Airport has massive regional signal
        {"max_dist_m": 2000, "base_boost": 0.35},
        {"max_dist_m": 6000, "base_boost": 0.18},
        {"max_dist_m": 12000,"base_boost": 0.07},
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════
def load_data():
    log.info("Loading classified grid and feature matrix ...")
    df_class = pd.read_parquet(C.PATHS["classified_grid"])

    df = df_class.copy()

    # commercial already in classified_grid — if not, load from potential_features
    if "commercial" not in df.columns:
        df_feat = pd.read_parquet(C.PATHS["potential_features"])
        df = df.merge(df_feat[["cell_id", "commercial"]], on="cell_id")

    # load grid for spatial joins
    grid = gpd.read_file(C.PATHS["grid_geojson"]).to_crs(C.CRS_METRIC)
    grid = grid.merge(df[["cell_id"]], on="cell_id")

    cx = grid.geometry.centroid.x.values
    cy = grid.geometry.centroid.y.values

    log.info(f"Loaded {len(df):,} cells")
    return df, grid, cx, cy


# ══════════════════════════════════════════════════════════════════════════════
# 2. COMPUTE IMPACT FOR ONE SCENARIO
# ══════════════════════════════════════════════════════════════════════════════
def compute_scenario_impact(scenario_key, scenario_cfg, df, cx, cy):
    log.info(f"Simulating: {scenario_cfg['label']} ...")

    sc_type   = scenario_cfg.get("type", "metro")
    zones     = ZONES_BY_TYPE[sc_type]
    stations  = scenario_cfg["stations"]
    N         = len(cx)
    cell_xy   = np.column_stack([cx, cy])

    # convert station coords to metric CRS
    station_geo = gpd.GeoDataFrame(
        geometry=[Point(s["lon"], s["lat"]) for s in stations],
        crs=C.CRS_GEO
    ).to_crs(C.CRS_METRIC)
    st_xy = np.column_stack([station_geo.geometry.x,
                              station_geo.geometry.y])

    # for each cell find min distance to any station
    tree    = cKDTree(st_xy)
    min_dist, _ = tree.query(cell_xy, k=1)

    # base boost from distance zones
    boost = np.zeros(N)
    for zone in zones:
        mask          = min_dist <= zone["max_dist_m"]
        boost[mask]   = np.maximum(boost[mask], zone["base_boost"])

    # smooth decay within each zone
    max_dist = zones[-1]["max_dist_m"]
    in_range = min_dist <= max_dist
    decay    = np.where(
        in_range,
        np.exp(-3.0 * min_dist / max_dist),
        0.0
    )
    boost = boost * decay / decay.max() if decay.max() > 0 else boost

    # commercial intensity multiplier
    comm = df["commercial"].values
    multiplier = np.where(
        comm > 0.6, C.COMMERCIAL_BOOST_MULTIPLIER_HIGH,
        np.where(comm > 0.3, C.COMMERCIAL_BOOST_MULTIPLIER_MED,
                 C.COMMERCIAL_BOOST_MULTIPLIER_LOW)
    )
    boost = boost * multiplier

    # spillover to neighbours
    radius   = 2 * np.sqrt(2) * C.GRID_SIZE_M * 1.05
    nb_tree  = cKDTree(cell_xy)
    pairs    = nb_tree.query_ball_point(cell_xy, r=radius)
    spillover = np.zeros(N)
    for i, neighbours in enumerate(pairs):
        if boost[i] > 0 and neighbours:
            nb = np.array([n for n in neighbours if n != i])
            if len(nb) > 0:
                spillover[nb] += C.SPILLOVER_FRACTION * boost[i] / len(nb)

    total_boost = boost + spillover

    # stats
    affected     = (total_boost > 0.05).sum()
    max_impact   = total_boost.max()
    mean_impact  = total_boost[total_boost > 0].mean() if affected > 0 else 0

    log.info(f"  Type: {sc_type} | Stations: {len(stations)}")
    log.info(f"  Cells affected (>0.05): {affected:,}")
    log.info(f"  Max impact: {max_impact:.4f}")
    log.info(f"  Mean impact (affected): {mean_impact:.4f}")

    return total_boost


# ══════════════════════════════════════════════════════════════════════════════
# 3. RECLASSIFY AFTER SCENARIO
# ══════════════════════════════════════════════════════════════════════════════
def reclassify_after_scenario(df, boost):
    """
    After boosting growth scores, recompute trajectory classification.
    Returns count of cells that changed trajectory.
    """
    new_score = np.clip(df["predicted_growth"].values + boost, 0, 1)
    new_delta = new_score - df["growth_score"].values

    t = C.TRAJECTORY
    score_low  = np.percentile(new_score, t["emerging_score_pct"])
    score_high = np.percentile(new_score, t["accelerating_score_pct"])
    delta_up   = np.percentile(new_delta, t["rising_delta_pct"])
    delta_dn   = np.percentile(new_delta, t["declining_delta_pct"])

    conditions = [
        (new_score <  score_low)  & (new_delta > delta_up),
        (new_score >= score_high) & (new_delta > delta_up),
        (new_delta < delta_dn),
    ]
    choices = ["Emerging", "Accelerating", "Declining"]
    new_traj = np.select(conditions, choices, default="Stable")

    changed = (new_traj != df["trajectory"].values).sum()
    log.info(f"  Cells reclassified: {changed:,}")

    return new_traj, changed


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("=" * 55)
    log.info("IUD-NEPS  --  Step 6: Scenario Simulation")
    log.info("=" * 55)

    log.info("--- [1/2] Loading Data ---")
    df, grid, cx, cy = load_data()

    log.info("--- [2/2] Running Scenarios ---")
    results = []

    for key, cfg in C.SCENARIOS.items():
        log.info("-" * 40)
        boost = compute_scenario_impact(key, cfg, df, cx, cy)
        new_traj, changed = reclassify_after_scenario(df, boost)

        # store per-cell results
        df[f"boost_{key}"]  = boost
        df[f"traj_{key}"]   = new_traj

        results.append({
            "scenario_key":   key,
            "scenario_label": cfg["label"],
            "type":           cfg.get("type", "metro"),
            "n_stations":     len(cfg["stations"]),
            "cells_affected": int((boost > 0.05).sum()),
            "max_impact":     float(boost.max()),
            "mean_impact":    float(boost[boost > 0.05].mean()) if (boost > 0.05).any() else 0,
            "cells_reclassified": int(changed),
        })

    # save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(C.PATHS["scenario_results"], index=False)
    df.to_parquet(C.PATHS["classified_grid"], index=False)

    # summary table
    log.info("=" * 55)
    log.info("Scenario Summary:")
    log.info(f"  {'Scenario':<40} {'Affected':>9} {'Max':>7} {'Reclassified':>14}")
    log.info(f"  {'-'*40} {'-'*9} {'-'*7} {'-'*14}")
    for _, row in results_df.iterrows():
        log.info(f"  {row['scenario_label'][:40]:<40} "
                 f"{row['cells_affected']:>9,} "
                 f"{row['max_impact']:>7.4f} "
                 f"{row['cells_reclassified']:>14,}")

    log.info("=" * 55)
    log.info("Simulation complete")
    log.info("Next: py -3.12 scripts/dashboard.py")
    log.info("=" * 55)