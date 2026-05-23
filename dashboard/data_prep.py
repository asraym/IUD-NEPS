"""
dashboard/data_prep.py
Loads all pipeline outputs and prepares them for the dashboard.
"""

import json
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C


def load_all(log):
    log.info("Loading pipeline outputs ...")

    df_class = pd.read_parquet(C.PATHS["classified_grid"])
    df_pot   = pd.read_parquet(C.PATHS["potential_features"])
    df_liv   = pd.read_parquet(C.PATHS["livability_features"])
    df_prop  = pd.read_csv(C.PATHS["property_csv"])
    df_shap  = pd.read_csv(C.PATHS["shap_values"])

    log.info(f"classified_grid columns: {list(df_class.columns)}")
    log.info(f"livability columns: {list(df_liv.columns)}")

    pot_cols = ["cell_id", "accessibility", "airport_proximity",
                "dmrc_proximity", "migration_rate",
                "median_income", "pop_density", "working_age_frac",
                "edu_index", "svc_education", "svc_healthcare",
                "svc_recreation", "svc_civic"]

    # livability sub-scores — exclude livability_score since it's already in df_class
    liv_sub_cols = ["cell_id", "aqi_score", "parks_score", "healthcare_score",
                    "education_score", "recreation_score", "civic_score",
                    "crime_proxy_score"]

    pot_cols     = [c for c in pot_cols     if c in df_pot.columns]
    liv_sub_cols = [c for c in liv_sub_cols if c in df_liv.columns]

    df = (df_class
          .merge(df_pot[pot_cols],     on="cell_id")
          .merge(df_liv[liv_sub_cols], on="cell_id"))

    # ensure livability_score is present
    if "livability_score" not in df.columns:
        log.info("livability_score not in classified_grid — loading from livability parquet")
        df = df.merge(df_liv[["cell_id", "livability_score"]], on="cell_id")

    # attach nearest ward property price
    ward_coords = df_prop[["lat", "lon"]].values
    cell_coords = df[["cy_lat", "cx_lon"]].values
    tree        = cKDTree(ward_coords)
    dists, idxs = tree.query(cell_coords, k=1)

    df["ward_name"]    = df_prop["ward"].values[idxs]
    df["price_2023"]   = df_prop["price_2023"].values[idxs]
    df["price_2021"]   = df_prop["price_2021"].values[idxs]
    df["price_cagr"]   = ((df_prop["price_2023"].values[idxs] /
                           df_prop["price_2021"].values[idxs])**(0.5) - 1) * 100
    df["ward_dist_km"] = dists / 1000

    # valuation tag
    price_norm = ((df["price_2023"] - df["price_2023"].min()) /
                  (df["price_2023"].max() - df["price_2023"].min()))
    diff = df["predicted_growth"].values - price_norm.values
    df["valuation"] = np.where(diff >  0.15, "Undervalued",
                      np.where(diff < -0.15, "Overvalued", "Fairly Valued"))

    log.info(f"Loaded {len(df):,} cells")
    return df, df_shap, df_prop


def prepare_stats(df):
    traj = df["trajectory"].value_counts().to_dict()
    return {
        "total_cells":    len(df),
        "accelerating":   int(traj.get("Accelerating", 0)),
        "emerging":       int(traj.get("Emerging",     0)),
        "stable":         int(traj.get("Stable",       0)),
        "declining":      int(traj.get("Declining",    0)),
        "avg_potential":  round(float(df["predicted_growth"].mean()), 3),
        "avg_livability": round(float(df["livability_score"].mean()),  3),
        "avg_combined":   round(float(df["combined_score"].mean()),    3),
        "undervalued":    int((df["valuation"] == "Undervalued").sum()),
        "overvalued":     int((df["valuation"] == "Overvalued").sum()),
    }


def prepare_shap(df_shap):
    top15 = df_shap.head(15)
    return {
        "labels": top15["feature"].tolist(),
        "values": [round(float(v), 5) for v in top15["mean_abs_shap"]],
    }


def prepare_scenarios(df):
    out = []
    for key, cfg in C.SCENARIOS.items():
        col = f"boost_{key}"
        if col not in df.columns:
            continue
        boost = df[col].values
        traj_col = f"traj_{key}"
        reclassified = int((df[traj_col] != df["trajectory"]).sum()) \
                       if traj_col in df.columns else 0
        out.append({
            "key":          key,
            "label":        cfg["label"].replace("\u2192", "->"),
            "color":        cfg["color"],
            "type":         cfg.get("type", "metro"),
            "affected":     int((boost > 0.05).sum()),
            "max_impact":   round(float(boost.max()), 4),
            "mean_impact":  round(float(boost[boost > 0.05].mean())
                                  if (boost > 0.05).any() else 0, 4),
            "reclassified": reclassified,
        })
    return out