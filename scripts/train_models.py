"""
train_models.py  —  IUD-NEPS Step 4: Model Training
====================================================
Trains XGBoost + LightGBM ensemble on growth potential score.
Uses 10-fold spatial block cross-validation.
Runs SHAP feature importance analysis.

Run from project root:
    py -3.12 scripts/train_models.py
"""

import os
import sys
import json
import time
import logging
import warnings
import numpy as np
import pandas as pd
import pickle

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
        logging.FileHandler(os.path.join(C.BASE_DIR, "train_models.log"), mode="w"),
    ]
)
log = logging.getLogger("iud-neps")


# ══════════════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ══════════════════════════════════════════════════════════════════════════════
def load_data():
    log.info("Loading feature matrix ...")
    df = pd.read_parquet(C.PATHS["potential_features"])

    with open(C.PATHS["feature_cols"]) as f:
        feature_cols = json.load(f)["potential"]

    X = df[feature_cols].values
    y = df["growth_score"].values
    coords = df[["cx_lon", "cy_lat"]].values

    log.info(f"Loaded: {X.shape[0]:,} cells x {X.shape[1]} features")
    log.info(f"Target: mean={y.mean():.3f}, std={y.std():.3f}")
    return X, y, coords, feature_cols, df


# ══════════════════════════════════════════════════════════════════════════════
# 2. SPATIAL BLOCK CROSS-VALIDATION  (k-means on centroids)
# ══════════════════════════════════════════════════════════════════════════════
def make_spatial_blocks(coords, n_blocks):
    log.info(f"Creating {n_blocks} spatial blocks via k-means ...")
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=n_blocks, random_state=C.RANDOM_SEED, n_init=10)
    blocks = km.fit_predict(coords)
    for b in range(n_blocks):
        log.info(f"  Block {b+1:2d}: {(blocks==b).sum():,} cells")
    return blocks


# ══════════════════════════════════════════════════════════════════════════════
# 3. TRAIN & EVALUATE
# ══════════════════════════════════════════════════════════════════════════════
def train_and_evaluate(X, y, blocks):
    from xgboost import XGBRegressor
    from lightgbm import LGBMRegressor
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

    n_blocks  = C.N_CV_BLOCKS
    w         = C.XGB_ENSEMBLE_WEIGHT

    # store out-of-fold predictions
    oof_xgb    = np.zeros(len(y))
    oof_lgbm   = np.zeros(len(y))
    oof_ensemble = np.zeros(len(y))
    oof_ridge  = np.zeros(len(y))
    oof_rf     = np.zeros(len(y))

    fold_metrics = []

    log.info("Starting 10-fold spatial block cross-validation ...")
    log.info(f"Models: XGBoost (w={w:.2f}) + LightGBM (w={1-w:.2f}) ensemble")

    for fold in range(n_blocks):
        t0       = time.time()
        val_mask = blocks == fold
        tr_mask  = ~val_mask

        X_tr, y_tr = X[tr_mask], y[tr_mask]
        X_val, y_val = X[val_mask], y[val_mask]

        # XGBoost
        xgb = XGBRegressor(**C.XGBOOST_PARAMS)
        xgb.fit(X_tr, y_tr,
                eval_set=[(X_val, y_val)],
                verbose=False)
        p_xgb = xgb.predict(X_val)

        # LightGBM
        lgbm = LGBMRegressor(**C.LIGHTGBM_PARAMS)
        lgbm.fit(X_tr, y_tr,
                 eval_set=[(X_val, y_val)],
                 callbacks=[])
        p_lgbm = lgbm.predict(X_val)

        # Ridge baseline
        ridge = Ridge(alpha=C.RIDGE_ALPHA)
        ridge.fit(X_tr, y_tr)
        p_ridge = ridge.predict(X_val)

        # Random Forest baseline
        rf = RandomForestRegressor(**C.RANDOM_FOREST_PARAMS)
        rf.fit(X_tr, y_tr)
        p_rf = rf.predict(X_val)

        # Ensemble
        p_ens = w * p_xgb + (1 - w) * p_lgbm

        # store OOF
        oof_xgb[val_mask]      = p_xgb
        oof_lgbm[val_mask]     = p_lgbm
        oof_ensemble[val_mask] = p_ens
        oof_ridge[val_mask]    = p_ridge
        oof_rf[val_mask]       = p_rf

        r2  = r2_score(y_val, p_ens)
        rmse= np.sqrt(mean_squared_error(y_val, p_ens))
        elapsed = time.time() - t0

        fold_metrics.append({"fold": fold+1, "r2": r2, "rmse": rmse,
                              "n_val": val_mask.sum()})
        log.info(f"  Fold {fold+1:2d}/{n_blocks} | R2={r2:.4f} | "
                 f"RMSE={rmse:.4f} | n={val_mask.sum():,} | {elapsed:.1f}s")

    # Overall metrics
    def metrics(y_true, y_pred, label):
        r2   = r2_score(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae  = mean_absolute_error(y_true, y_pred)
        log.info(f"  {label:20s} R2={r2:.4f}  RMSE={rmse:.4f}  MAE={mae:.4f}")
        return {"r2": r2, "rmse": rmse, "mae": mae}

    log.info("=" * 55)
    log.info("Overall OOF Performance:")
    m_ridge = metrics(y, oof_ridge,    "Ridge")
    m_rf    = metrics(y, oof_rf,       "Random Forest")
    m_xgb   = metrics(y, oof_xgb,      "XGBoost")
    m_lgbm  = metrics(y, oof_lgbm,     "LightGBM")
    m_ens   = metrics(y, oof_ensemble, "Ensemble")
    log.info("=" * 55)

    return {
        "fold_metrics":   fold_metrics,
        "overall": {
            "ridge":    m_ridge,
            "rf":       m_rf,
            "xgb":      m_xgb,
            "lgbm":     m_lgbm,
            "ensemble": m_ens,
        },
        "oof_predictions": oof_ensemble,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. TRAIN FINAL MODELS ON FULL DATA
# ══════════════════════════════════════════════════════════════════════════════
def train_final_models(X, y):
    from xgboost import XGBRegressor
    from lightgbm import LGBMRegressor

    log.info("Training final models on full dataset ...")

    xgb = XGBRegressor(**C.XGBOOST_PARAMS)
    xgb.fit(X, y, verbose=False)
    with open(C.PATHS["xgb_model"], "wb") as f:
        pickle.dump(xgb, f)
    log.info("XGBoost final model saved")

    lgbm = LGBMRegressor(**C.LIGHTGBM_PARAMS)
    lgbm.fit(X, y)
    with open(C.PATHS["lgbm_model"], "wb") as f:
        pickle.dump(lgbm, f)
    log.info("LightGBM final model saved")

    return xgb, lgbm


# ══════════════════════════════════════════════════════════════════════════════
# 5. SHAP ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
def run_shap(xgb_model, X, feature_cols):
    log.info("Running SHAP analysis ...")
    import shap

    # use a sample for speed if dataset is large
    n_sample = min(2000, len(X))
    idx      = np.random.RandomState(C.RANDOM_SEED).choice(len(X), n_sample, replace=False)
    X_sample = X[idx]

    explainer   = shap.TreeExplainer(xgb_model)
    shap_values = explainer.shap_values(X_sample)

    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    shap_df = pd.DataFrame({
        "feature":    feature_cols,
        "mean_abs_shap": mean_abs_shap
    }).sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)

    shap_df.to_csv(C.PATHS["shap_values"], index=False)

    log.info("Top 10 features by SHAP importance:")
    for _, row in shap_df.head(10).iterrows():
        bar = "#" * int(row["mean_abs_shap"] * 500)
        log.info(f"  {row['feature']:30s} {row['mean_abs_shap']:.5f}  {bar}")

    return shap_df


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("=" * 55)
    log.info("IUD-NEPS  --  Step 4: Model Training")
    log.info("=" * 55)
    overall_start = time.time()

    log.info("--- [1/4] Loading Data ---")
    X, y, coords, feature_cols, df = load_data()

    log.info("--- [2/4] Cross-Validation ---")
    blocks  = make_spatial_blocks(coords, C.N_CV_BLOCKS)
    results = train_and_evaluate(X, y, blocks)

    log.info("--- [3/4] Training Final Models ---")
    xgb_model, lgbm_model = train_final_models(X, y)

    log.info("--- [4/4] SHAP Analysis ---")
    shap_df = run_shap(xgb_model, X, feature_cols)

    # save metrics
    with open(C.PATHS["cv_metrics"], "w") as f:
        json.dump(results["overall"], f, indent=2)
    log.info("CV metrics saved")

    # save OOF predictions back to features file
    df["predicted_growth"] = results["oof_predictions"]
    df.to_parquet(C.PATHS["potential_features"], index=False)
    log.info("OOF predictions saved to feature matrix")

    elapsed = (time.time() - overall_start) / 60
    log.info("=" * 55)
    log.info(f"Training complete in {elapsed:.1f} mins")
    log.info(f"Ensemble R2:   {results['overall']['ensemble']['r2']:.4f}")
    log.info(f"Ensemble RMSE: {results['overall']['ensemble']['rmse']:.4f}")
    log.info("Next: py -3.12 scripts/classify.py")
    log.info("=" * 55)