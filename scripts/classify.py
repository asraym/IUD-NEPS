"""
classify.py  —  IUD-NEPS Step 5: Trajectory Classification
===========================================================
Classifies each grid cell into one of four evolutionary states:
  - Emerging      (low current score, rising fast)
  - Accelerating  (high current score, rising fast)
  - Stable        (not changing much)
  - Declining     (falling)

Uses percentile-based thresholds to fix the 92%-stable problem
from the original paper.

Also computes the final combined score (potential + livability blend).

Run from project root:
    py -3.12 scripts/classify.py
"""

import os
import sys
import logging
import warnings
import numpy as np
import pandas as pd

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
        logging.FileHandler(os.path.join(C.BASE_DIR, "classify.log"), mode="w"),
    ]
)
log = logging.getLogger("iud-neps")


# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════
def load_data():
    log.info("Loading potential and livability features ...")
    df_pot = pd.read_parquet(C.PATHS["potential_features"])
    df_liv = pd.read_parquet(C.PATHS["livability_features"])

    # merge on cell_id
    df = df_pot[["cell_id", "cx_lon", "cy_lat",
                 "growth_score", "predicted_growth"]].copy()
    df = df.merge(df_liv[["cell_id", "livability_score"]], on="cell_id")

    log.info(f"Loaded {len(df):,} cells")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 2. COMPUTE DELTA  (predicted - actual growth score)
# ══════════════════════════════════════════════════════════════════════════════
def compute_delta(df):
    """
    delta_G = predicted_growth - growth_score
    Positive delta = model predicts higher growth than current score suggests
    = cell is undervalued / rising
    """
    df["delta_G"] = df["predicted_growth"] - df["growth_score"]
    log.info(f"Delta G: mean={df['delta_G'].mean():.4f}, "
             f"std={df['delta_G'].std():.4f}, "
             f"range=[{df['delta_G'].min():.4f}, {df['delta_G'].max():.4f}]")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 3. PERCENTILE-BASED CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════
def classify_trajectories(df):
    """
    Percentile-based thresholds — avoids the 92%-stable problem.

    Score percentiles split cells into low/high current growth.
    Delta percentiles split cells into rising/falling.

    Emerging     = low score  + high delta  (undervalued, heating up)
    Accelerating = high score + high delta  (already strong, getting stronger)
    Declining    = low delta  (falling regardless of current score)
    Stable       = everything else
    """
    t = C.TRAJECTORY

    score_low_thresh  = np.percentile(df["growth_score"], t["emerging_score_pct"])
    score_high_thresh = np.percentile(df["growth_score"], t["accelerating_score_pct"])
    delta_up_thresh   = np.percentile(df["delta_G"],      t["rising_delta_pct"])
    delta_dn_thresh   = np.percentile(df["delta_G"],      t["declining_delta_pct"])

    log.info(f"Thresholds:")
    log.info(f"  Score low  (p{t['emerging_score_pct']}):     {score_low_thresh:.4f}")
    log.info(f"  Score high (p{t['accelerating_score_pct']}):     {score_high_thresh:.4f}")
    log.info(f"  Delta up   (p{t['rising_delta_pct']}):     {delta_up_thresh:.4f}")
    log.info(f"  Delta down (p{t['declining_delta_pct']}):     {delta_dn_thresh:.4f}")

    conditions = [
        (df["growth_score"] <  score_low_thresh)  & (df["delta_G"] > delta_up_thresh),
        (df["growth_score"] >= score_high_thresh) & (df["delta_G"] > delta_up_thresh),
        (df["delta_G"] < delta_dn_thresh),
    ]
    choices = ["Emerging", "Accelerating", "Declining"]
    df["trajectory"] = np.select(conditions, choices, default="Stable")

    # summary
    counts = df["trajectory"].value_counts()
    total  = len(df)
    log.info("Trajectory distribution:")
    for traj in ["Accelerating", "Emerging", "Stable", "Declining"]:
        n   = counts.get(traj, 0)
        pct = 100 * n / total
        bar = "#" * int(pct / 2)
        log.info(f"  {traj:15s} {n:5,}  ({pct:5.1f}%)  {bar}")

    return df


# ══════════════════════════════════════════════════════════════════════════════
# 4. COMBINED SCORE  (blended potential + livability)
# ══════════════════════════════════════════════════════════════════════════════
def compute_combined_score(df, potential_weight=0.6, livability_weight=0.4):
    """
    Combined score for the 'overall best areas' view in the dashboard.
    Default: 60% growth potential, 40% livability.
    Weights are configurable in the dashboard.
    """
    df["combined_score"] = (potential_weight  * df["predicted_growth"] +
                            livability_weight * df["livability_score"])
    # normalise to [0, 1]
    mn = df["combined_score"].min()
    mx = df["combined_score"].max()
    df["combined_score"] = (df["combined_score"] - mn) / (mx - mn)

    log.info(f"Combined score (w_pot={potential_weight}, w_liv={livability_weight}):")
    log.info(f"  mean={df['combined_score'].mean():.3f}, "
             f"std={df['combined_score'].std():.3f}")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 5. RANK CELLS
# ══════════════════════════════════════════════════════════════════════════════
def rank_cells(df):
    df["potential_rank"]  = df["predicted_growth"].rank(ascending=False).astype(int)
    df["livability_rank"] = df["livability_score"].rank(ascending=False).astype(int)
    df["combined_rank"]   = df["combined_score"].rank(ascending=False).astype(int)
    log.info("Cell rankings computed")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("=" * 55)
    log.info("IUD-NEPS  --  Step 5: Classification")
    log.info("=" * 55)

    log.info("--- [1/4] Loading Data ---")
    df = load_data()

    log.info("--- [2/4] Computing Delta ---")
    df = compute_delta(df)

    log.info("--- [3/4] Classifying Trajectories ---")
    df = classify_trajectories(df)

    log.info("--- [4/4] Combined Score + Rankings ---")
    df = compute_combined_score(df)
    df = rank_cells(df)

    # save
    df.to_parquet(C.PATHS["classified_grid"], index=False)
    log.info(f"Classified grid saved -> {C.PATHS['classified_grid']}")

    # top 10 cells overall
    log.info("Top 10 cells by combined score:")
    top10 = df.nsmallest(10, "combined_rank")[
        ["cell_id", "cx_lon", "cy_lat", "trajectory",
         "predicted_growth", "livability_score", "combined_score"]
    ]
    for _, row in top10.iterrows():
        log.info(f"  Cell {row['cell_id']:5d} | "
                 f"lat={row['cy_lat']:.4f} lon={row['cx_lon']:.4f} | "
                 f"{row['trajectory']:12s} | "
                 f"pot={row['predicted_growth']:.3f} | "
                 f"liv={row['livability_score']:.3f} | "
                 f"combined={row['combined_score']:.3f}")

    log.info("=" * 55)
    log.info("Classification complete")
    log.info("Next: py -3.12 scripts/simulate.py")
    log.info("=" * 55)