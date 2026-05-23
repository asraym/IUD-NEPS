"""
config.py — IUD-NEPS Central Configuration
===========================================
Single source of truth for the entire pipeline.
Edit this file to change any setting — no need to touch individual scripts.
"""

import os

# ══════════════════════════════════════════════════════════════════════════════
# STUDY AREA
# ══════════════════════════════════════════════════════════════════════════════
BBOX = {
    "north": 28.88,
    "south": 28.40,
    "east":  77.35,
    "west":  76.80,
}
CRS_METRIC = "EPSG:32643"   # UTM Zone 43N (metres) — for distance calculations
CRS_GEO    = "EPSG:4326"

# Accessibility mode — set True only if road network download succeeds
USE_ROAD_NETWORK = False    # WGS-84 (lat/lon)      — for mapping
GRID_SIZE_M = 500           # cell size in metres


# ══════════════════════════════════════════════════════════════════════════════
# ECONOMIC CENTRES  (accessibility targets for Growth Potential Score)
# ══════════════════════════════════════════════════════════════════════════════
ECONOMIC_CENTRES = [
    {"name": "Connaught Place",     "lat": 28.6315, "lon": 77.2167, "weight": 1.00},
    {"name": "Noida Sector 18",     "lat": 28.5700, "lon": 77.3200, "weight": 0.85},
    {"name": "Gurgaon Cyber City",  "lat": 28.4950, "lon": 77.0880, "weight": 0.80},
    {"name": "South Delhi Saket",   "lat": 28.5245, "lon": 77.2066, "weight": 0.70},
    {"name": "Ghaziabad Raj Nagar", "lat": 28.6620, "lon": 77.4220, "weight": 0.65},
    {"name": "Karol Bagh",          "lat": 28.6530, "lon": 77.1900, "weight": 0.60},
    {"name": "Rohini",              "lat": 28.7350, "lon": 77.1200, "weight": 0.55},
]


# ══════════════════════════════════════════════════════════════════════════════
# AIRPORTS  (higher weight for Growth Potential Score)
# ══════════════════════════════════════════════════════════════════════════════
AIRPORTS = [
    {"name": "IGI Airport",     "lat": 28.5562, "lon": 77.1000, "weight": 1.00},
    {"name": "Hindon Air Base", "lat": 28.6952, "lon": 77.3726, "weight": 0.50},
    {"name": "Jewar Airport",   "lat": 28.1200, "lon": 77.6000, "weight": 0.70},
]


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════
SERVICE_KERNEL_BANDWIDTH_M = 800
SPATIAL_LAG_ALPHA          = 0.003
IDW_NEIGHBOURS             = 4


# ══════════════════════════════════════════════════════════════════════════════
# GROWTH POTENTIAL SCORE  — target variable weights
# ══════════════════════════════════════════════════════════════════════════════
GROWTH_SCORE_WEIGHTS = {
    "price_cagr":   0.60,
    "sale_density": 0.40,
}


# ══════════════════════════════════════════════════════════════════════════════
# LIVABILITY SCORE  — weighted composite index (weights must sum to 1.0)
# ══════════════════════════════════════════════════════════════════════════════
LIVABILITY_WEIGHTS = {
    "aqi":         0.25,
    "healthcare":  0.25,
    "education":   0.15,
    "parks":       0.10,
    "recreation":  0.10,
    "civic":       0.10,
    "crime_proxy": 0.05,
}

# Data quality flags — shown in dashboard
LIVABILITY_DATA_QUALITY = {
    "aqi":         "estimated",   # 20 monitoring zones IDW interpolated
    "healthcare":  "good",        # 1,693 OSM POIs
    "education":   "good",        # 361 OSM POIs
    "parks":       "weak",        # only 114 OSM POIs — undertagged in India
    "recreation":  "moderate",    # 329 OSM POIs
    "civic":       "moderate",    # 282 OSM POIs
    "crime_proxy": "estimated",   # district-level proxy, not ward-level
}


# ══════════════════════════════════════════════════════════════════════════════
# ML MODELS
# ══════════════════════════════════════════════════════════════════════════════
N_CV_BLOCKS = 10
RANDOM_SEED = 42

XGBOOST_PARAMS = {
    "n_estimators":      620,
    "max_depth":         5,
    "learning_rate":     0.047,
    "subsample":         0.82,
    "colsample_bytree":  0.74,
    "reg_lambda":        2.3,
    "reg_alpha":         0.4,
    "min_child_weight":  3,
    "objective":         "reg:squarederror",
    "random_state":      RANDOM_SEED,
    "n_jobs":            -1,
}

LIGHTGBM_PARAMS = {
    "n_estimators":      600,
    "max_depth":         5,
    "learning_rate":     0.05,
    "subsample":         0.80,
    "colsample_bytree":  0.75,
    "reg_lambda":        2.0,
    "reg_alpha":         0.3,
    "min_child_samples": 20,
    "random_state":      RANDOM_SEED,
    "n_jobs":            -1,
    "verbose":           -1,
}

# Final prediction = XGB_WEIGHT * xgb_pred + (1 - XGB_WEIGHT) * lgbm_pred
RIDGE_ALPHA = 1.0

RANDOM_FOREST_PARAMS = {
    "n_estimators": 200,
    "random_state": RANDOM_SEED,
    "n_jobs":       -1,
}

XGB_ENSEMBLE_WEIGHT = 0.55


# ══════════════════════════════════════════════════════════════════════════════
# TRAJECTORY CLASSIFICATION  (percentile-based — fixes the 92% stable problem)
# ══════════════════════════════════════════════════════════════════════════════
TRAJECTORY = {
    "emerging_score_pct":     33,
    "accelerating_score_pct": 67,
    "rising_delta_pct":       60,
    "declining_delta_pct":    35,
}


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO SIMULATION
# ══════════════════════════════════════════════════════════════════════════════
SCENARIO_ZONES = [
    {"max_dist_m": 800,  "base_boost": 0.25, "label": "Walk catchment"},
    {"max_dist_m": 2000, "base_boost": 0.12, "label": "Feeder zone"},
    {"max_dist_m": 4000, "base_boost": 0.04, "label": "Regional signal"},
]

SPILLOVER_FRACTION = 0.30

COMMERCIAL_BOOST_MULTIPLIER_HIGH = 1.4   # commercial intensity > 0.6
COMMERCIAL_BOOST_MULTIPLIER_MED  = 1.1   # 0.3 - 0.6
COMMERCIAL_BOOST_MULTIPLIER_LOW  = 0.85  # < 0.3

SCENARIOS = {
    "delhi_meerut_rrts": {
        # Already partially open — full opening covers massive East Delhi + Ghaziabad corridor
        "label": "Delhi-Meerut RRTS Full Opening",
        "color": "#E53935",
        "type": "rrts",
        "stations": [
            {"name": "Sarai Kale Khan",       "lat": 28.5950, "lon": 77.2500},
            {"name": "New Ashok Nagar",        "lat": 28.6100, "lon": 77.3100},
            {"name": "Anand Vihar",            "lat": 28.6469, "lon": 77.3152},
            {"name": "Ghaziabad",              "lat": 28.6692, "lon": 77.4538},
            {"name": "Guldhar",                "lat": 28.6820, "lon": 77.4750},
            {"name": "Duhai",                  "lat": 28.7000, "lon": 77.5000},
            {"name": "Muradnagar",             "lat": 28.7750, "lon": 77.5100},
            {"name": "Modi Nagar",             "lat": 28.8300, "lon": 77.5400},
            {"name": "Meerut South",           "lat": 28.8600, "lon": 77.6800},
        ],
    },
    "delhi_gurugram_rrts": {
        # Proposed — covers entire SW Delhi + Gurgaon corridor, huge impact
        "label": "Delhi-Gurugram RRTS Corridor",
        "color": "#00897B",
        "type": "rrts",
        "stations": [
            {"name": "Sarai Kale Khan",        "lat": 28.5950, "lon": 77.2500},
            {"name": "Munirka",                "lat": 28.5580, "lon": 77.1730},
            {"name": "Aerocity",               "lat": 28.5562, "lon": 77.1000},
            {"name": "Dwarka Sector 21",       "lat": 28.5521, "lon": 77.0588},
            {"name": "Kherki Daula",           "lat": 28.4380, "lon": 77.0020},
            {"name": "Gurgaon Sector 17",      "lat": 28.4595, "lon": 77.0266},
            {"name": "Manesar",                "lat": 28.3580, "lon": 76.9380},
        ],
    },
    "noida_metro_expansion": {
        # Proposed Noida Metro Phase 2 — covers large Noida + Greater Noida area
        "label": "Noida Metro Phase 2 Expansion",
        "color": "#1565C0",
        "type": "metro",
        "stations": [
            {"name": "Noida Sector 62",        "lat": 28.6270, "lon": 77.3730},
            {"name": "Noida Sector 70",        "lat": 28.6100, "lon": 77.3900},
            {"name": "Noida Sector 78",        "lat": 28.5950, "lon": 77.4050},
            {"name": "Noida Sector 101",       "lat": 28.5700, "lon": 77.3900},
            {"name": "Noida Sector 137",       "lat": 28.5400, "lon": 77.3800},
            {"name": "Greater Noida Sector 2", "lat": 28.5000, "lon": 77.4000},
            {"name": "Greater Noida Depot",    "lat": 28.4700, "lon": 77.4100},
            {"name": "Knowledge Park",         "lat": 28.4500, "lon": 77.4300},
        ],
    },
    "ring_road_metro": {
        # Proposed Ring Metro — circles central Delhi, affects entire city core
        "label": "Delhi Ring Road Metro Corridor",
        "color": "#F57C00",
        "type": "metro",
        "stations": [
            {"name": "Kashmere Gate",          "lat": 28.6680, "lon": 77.2280},
            {"name": "Indraprastha",           "lat": 28.6320, "lon": 77.2850},
            {"name": "Lajpat Nagar",           "lat": 28.5700, "lon": 77.2430},
            {"name": "Saket",                  "lat": 28.5245, "lon": 77.2066},
            {"name": "Dhaula Kuan",            "lat": 28.5913, "lon": 77.1553},
            {"name": "Rajouri Garden",         "lat": 28.6480, "lon": 77.1220},
            {"name": "Punjabi Bagh",           "lat": 28.6730, "lon": 77.1310},
            {"name": "Rohini West",            "lat": 28.7200, "lon": 77.1050},
            {"name": "Netaji Subhash Place",   "lat": 28.6950, "lon": 77.1580},
        ],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# FILE PATHS
# ══════════════════════════════════════════════════════════════════════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PATHS = {
    # raw data
    "road_graph":          os.path.join(BASE_DIR, "data/raw/road_network.graphml"),
    "pois_education":      os.path.join(BASE_DIR, "data/raw/pois_education.geojson"),
    "pois_healthcare":     os.path.join(BASE_DIR, "data/raw/pois_healthcare.geojson"),
    "pois_recreation":     os.path.join(BASE_DIR, "data/raw/pois_recreation.geojson"),
    "pois_civic":          os.path.join(BASE_DIR, "data/raw/pois_civic.geojson"),
    "pois_commercial":     os.path.join(BASE_DIR, "data/raw/pois_commercial.geojson"),
    "pois_parks":          os.path.join(BASE_DIR, "data/raw/pois_parks.geojson"),
    "property_csv":        os.path.join(BASE_DIR, "data/raw/ward_property_prices.csv"),
    "census_csv":          os.path.join(BASE_DIR, "data/raw/census_ward_data.csv"),
    "aqi_csv":             os.path.join(BASE_DIR, "data/raw/aqi_zone_data.csv"),
    "crime_csv":           os.path.join(BASE_DIR, "data/raw/crime_proxy_data.csv"),
    # processed
    "grid_geojson":        os.path.join(BASE_DIR, "data/processed/grid.geojson"),
    "potential_features":  os.path.join(BASE_DIR, "data/processed/potential_features.parquet"),
    "livability_features": os.path.join(BASE_DIR, "data/processed/livability_features.parquet"),
    "feature_cols":        os.path.join(BASE_DIR, "data/processed/feature_cols.json"),
    # models
    "xgb_model":           os.path.join(BASE_DIR, "models/potential_model/xgb.pkl"),
    "lgbm_model":          os.path.join(BASE_DIR, "models/potential_model/lgbm.pkl"),
    "cv_metrics":          os.path.join(BASE_DIR, "models/potential_model/cv_metrics.json"),
    "shap_values":         os.path.join(BASE_DIR, "models/potential_model/shap_values.csv"),
    # outputs
    "classified_grid":     os.path.join(BASE_DIR, "outputs/classified_grid.parquet"),
    "scenario_results":    os.path.join(BASE_DIR, "outputs/scenario_results.csv"),
    "dashboard":           os.path.join(BASE_DIR, "outputs/dashboard.html"),
}

for d in [
    os.path.join(BASE_DIR, "data/raw"),
    os.path.join(BASE_DIR, "data/processed"),
    os.path.join(BASE_DIR, "models/potential_model"),
    os.path.join(BASE_DIR, "models/livability_model"),
    os.path.join(BASE_DIR, "outputs"),
]:
    os.makedirs(d, exist_ok=True)