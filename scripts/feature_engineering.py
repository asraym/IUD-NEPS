"""
feature_engineering.py  —  IUD-NEPS Step 3: Feature Engineering
================================================================
Builds the full feature matrix for all grid cells:

  POTENTIAL SCORE features (28 total = 14 local + 14 spatial lag)
  ----------------------------------------------------------------
  1.  accessibility          — weighted Euclidean to 7 economic centres
  2.  airport_proximity      — weighted proximity to IGI, Hindon, Jewar
  3.  dmrc_proximity         — distance to nearest DMRC station
  4.  svc_education          — Gaussian kernel density of schools/colleges
  5.  svc_healthcare         — Gaussian kernel density of hospitals/clinics
  6.  svc_recreation         — Gaussian kernel density of recreation POIs
  7.  svc_civic              — Gaussian kernel density of civic amenities
  8.  svc_composite          — mean of 4 service sub-scores
  9.  commercial             — commercial POI count per cell
  10. pop_density            — population density (Census 2011 IDW)
  11. working_age_frac       — fraction aged 18-64 (Census 2011 IDW)
  12. edu_index              — education attainment index (Census 2011 IDW)
  13. median_income          — median household income (Census 2011 IDW)
  14. migration_rate         — net in-migration rate (Census 2011 IDW)
  + spatial lag of all 14 above

  LIVABILITY SCORE features (7)
  ----------------------------------------------------------------
  1.  aqi_score              — inverted AQI (lower pollution = higher score)
  2.  parks_score            — Gaussian kernel density of parks
  3.  healthcare_score       — same as svc_healthcare
  4.  education_score        — same as svc_education
  5.  recreation_score       — same as svc_recreation
  6.  civic_score            — same as svc_civic
  7.  crime_proxy_score      — inverted crime rate (IDW from district data)

  TARGET VARIABLE
  ----------------------------------------------------------------
  growth_score  — 0.6 * price_CAGR + 0.4 * sale_density + commercial_bonus

Run from project root:
    py -3.12 scripts/feature_engineering.py
"""

import os
import sys
import time
import json
import logging
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box, Point
from scipy.spatial import cKDTree

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
        logging.FileHandler(os.path.join(C.BASE_DIR, "feature_engineering.log"), mode="w"),
    ]
)
log = logging.getLogger("iud-neps")


# ══════════════════════════════════════════════════════════════════════════════
# 1. BUILD GRID
# ══════════════════════════════════════════════════════════════════════════════
def build_grid():
    if os.path.exists(C.PATHS["grid_geojson"]):
        log.info("Grid already exists — loading from cache.")
        grid = gpd.read_file(C.PATHS["grid_geojson"])
        log.info(f"Grid loaded: {len(grid):,} cells")
        return grid

    log.info("Building 500m x 500m grid ...")
    t0 = time.time()

    aoi = gpd.GeoDataFrame(
        geometry=[box(C.BBOX["west"], C.BBOX["south"],
                      C.BBOX["east"], C.BBOX["north"])],
        crs=C.CRS_GEO
    ).to_crs(C.CRS_METRIC)

    xmin, ymin, xmax, ymax = aoi.total_bounds
    s = C.GRID_SIZE_M

    cells = [
        box(x, y, x + s, y + s)
        for x in np.arange(xmin, xmax, s)
        for y in np.arange(ymin, ymax, s)
    ]

    grid = gpd.GeoDataFrame({"geometry": cells}, crs=C.CRS_METRIC)
    grid = gpd.clip(grid, aoi).reset_index(drop=True)
    grid["cell_id"] = np.arange(len(grid))

    # centroids in metric + geographic CRS
    cents = grid.geometry.centroid
    grid["cx_m"] = cents.x
    grid["cy_m"] = cents.y

    cents_geo = gpd.GeoSeries(cents, crs=C.CRS_METRIC).to_crs(C.CRS_GEO)
    grid["cx_lon"] = cents_geo.x
    grid["cy_lat"] = cents_geo.y

    grid.to_file(C.PATHS["grid_geojson"], driver="GeoJSON")
    log.info(f"Grid built: {len(grid):,} cells in {time.time()-t0:.1f}s")
    return grid


# ══════════════════════════════════════════════════════════════════════════════
# 2. ACCESSIBILITY  (Euclidean weighted travel time to economic centres)
# ══════════════════════════════════════════════════════════════════════════════
def compute_accessibility(cx, cy):
    log.info("Computing accessibility scores ...")
    SPEED_MS = 30 * 1000 / 3600   # assumed 30 km/h average speed

    acc = np.zeros(len(cx))
    for centre in C.ECONOMIC_CENTRES:
        pt = gpd.GeoDataFrame(
            geometry=[Point(centre["lon"], centre["lat"])], crs=C.CRS_GEO
        ).to_crs(C.CRS_METRIC)
        px, py   = pt.geometry.x[0], pt.geometry.y[0]
        dist_m   = np.sqrt((cx - px)**2 + (cy - py)**2)
        dist_m   = np.where(dist_m < 100, 100, dist_m)
        time_min = dist_m / SPEED_MS / 60
        acc     += centre["weight"] / time_min

    acc = _norm(acc)
    log.info("Accessibility computed")
    return acc


# ══════════════════════════════════════════════════════════════════════════════
# 3. AIRPORT PROXIMITY
# ══════════════════════════════════════════════════════════════════════════════
def compute_airport_proximity(cx, cy):
    log.info("Computing airport proximity ...")
    score = np.zeros(len(cx))

    for airport in C.AIRPORTS:
        pt = gpd.GeoDataFrame(
            geometry=[Point(airport["lon"], airport["lat"])], crs=C.CRS_GEO
        ).to_crs(C.CRS_METRIC)
        px, py  = pt.geometry.x[0], pt.geometry.y[0]
        dist_m  = np.sqrt((cx - px)**2 + (cy - py)**2)
        dist_m  = np.where(dist_m < 100, 100, dist_m)
        # inverse distance weighted by airport importance
        score  += airport["weight"] / (dist_m / 1000.0)

    score = _norm(score)
    log.info("Airport proximity computed")
    return score


# ══════════════════════════════════════════════════════════════════════════════
# 4. DMRC PROXIMITY
# ══════════════════════════════════════════════════════════════════════════════
DMRC_STATIONS = [
    # existing operational stations (approximate)
    (28.6315, 77.2167), (28.6530, 77.1900), (28.5700, 77.2430),
    (28.5245, 77.2066), (28.5521, 77.0588), (28.7350, 77.1200),
    (28.5700, 77.3200), (28.4950, 77.0880), (28.6620, 77.4220),
    (28.5885, 77.2510), (28.6075, 77.2950), (28.5400, 77.2600),
    (28.6270, 77.0820), (28.6200, 77.0500), (28.5900, 77.0870),
    (28.6469, 77.3152), (28.6730, 77.1310), (28.5650, 77.1870),
    (28.6139, 77.2090), (28.5921, 77.0460), (28.7010, 77.1310),
    (28.6430, 77.2950), (28.4820, 77.0730), (28.5480, 77.2580),
    (28.6680, 77.2280), (28.7100, 77.1020), (28.6350, 77.2850),
    (28.5780, 77.3150), (28.6920, 77.1580), (28.7250, 77.1450),
]

def compute_dmrc_proximity(cx, cy):
    log.info("Computing DMRC proximity ...")
    stations_geo = gpd.GeoDataFrame(
        geometry=[Point(lon, lat) for lat, lon in DMRC_STATIONS],
        crs=C.CRS_GEO
    ).to_crs(C.CRS_METRIC)

    st_xy    = np.column_stack([stations_geo.geometry.x, stations_geo.geometry.y])
    cell_xy  = np.column_stack([cx, cy])
    tree     = cKDTree(st_xy)
    dist_m, _ = tree.query(cell_xy, k=1)

    # proximity = 1 / (1 + dist_km)
    score = 1.0 / (1.0 + dist_m / 1000.0)
    score = _norm(score)
    log.info("DMRC proximity computed")
    return score


# ══════════════════════════════════════════════════════════════════════════════
# 5. SERVICE DENSITY  (Gaussian kernel per POI category)
# ══════════════════════════════════════════════════════════════════════════════
def compute_service_density(cx, cy, poi_key):
    sigma    = C.SERVICE_KERNEL_BANDWIDTH_M
    search_r = 3 * sigma
    cell_xy  = np.column_stack([cx, cy])

    try:
        gdf = gpd.read_file(C.PATHS[poi_key])
        if len(gdf) == 0:
            raise ValueError("empty")
        gdf_m  = gdf.to_crs(C.CRS_METRIC)
        poi_xy = np.column_stack([gdf_m.geometry.x, gdf_m.geometry.y])
        tree   = cKDTree(poi_xy)
        scores = np.zeros(len(cx))
        pairs  = tree.query_ball_point(cell_xy, r=search_r)
        for i, nb in enumerate(pairs):
            if nb:
                d = np.sqrt(((cell_xy[i] - poi_xy[nb])**2).sum(axis=1))
                scores[i] = np.sum(np.exp(-(d**2) / (2 * sigma**2)))
        return _norm(scores)
    except Exception as e:
        log.warning(f"  {poi_key} density failed ({e}) — using zeros")
        return np.zeros(len(cx))


# ══════════════════════════════════════════════════════════════════════════════
# 6. COMMERCIAL INTENSITY  (POI count per cell)
# ══════════════════════════════════════════════════════════════════════════════
def compute_commercial(grid):
    log.info("Computing commercial intensity ...")
    try:
        gdf   = gpd.read_file(C.PATHS["pois_commercial"]).to_crs(C.CRS_METRIC)
        joined = gpd.sjoin(gdf, grid[["cell_id", "geometry"]],
                           how="left", predicate="within")
        counts = (joined.groupby("cell_id").size()
                        .reindex(grid["cell_id"], fill_value=0)
                        .values.astype(float))
    except Exception as e:
        log.warning(f"Commercial intensity failed ({e}) — using zeros")
        counts = np.zeros(len(grid))

    result = _norm(counts)
    log.info("Commercial intensity computed")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 7. DEMOGRAPHICS  (IDW interpolation from ward centroids)
# ══════════════════════════════════════════════════════════════════════════════
def compute_demographics(cx, cy):
    log.info("Computing demographic features ...")
    df      = pd.read_csv(C.PATHS["census_csv"])
    vars_   = ["pop_density", "working_age_frac", "edu_index",
                "median_income", "migration_rate"]

    ward_geo = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=C.CRS_GEO
    ).to_crs(C.CRS_METRIC)

    ward_xy  = np.column_stack([ward_geo.geometry.x, ward_geo.geometry.y])
    cell_xy  = np.column_stack([cx, cy])
    k        = C.IDW_NEIGHBOURS
    tree     = cKDTree(ward_xy)
    dists, idxs = tree.query(cell_xy, k=k)
    dists    = np.where(dists < 1, 1.0, dists)
    w        = 1.0 / dists**2
    w       /= w.sum(axis=1, keepdims=True)

    result = {}
    for var in vars_:
        vals       = df[var].values[idxs]
        interp     = (w * vals).sum(axis=1)
        result[var] = _norm(interp)

    log.info(f"Demographics computed ({len(vars_)} variables)")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 8. AQI SCORE  (inverted — lower AQI = higher livability)
# ══════════════════════════════════════════════════════════════════════════════
def compute_aqi_score(cx, cy):
    log.info("Computing AQI score ...")
    df = pd.read_csv(C.PATHS["aqi_csv"])
    df["aqi_avg"] = df[["aqi_2021", "aqi_2022", "aqi_2023"]].mean(axis=1)

    zone_geo = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=C.CRS_GEO
    ).to_crs(C.CRS_METRIC)

    zone_xy  = np.column_stack([zone_geo.geometry.x, zone_geo.geometry.y])
    cell_xy  = np.column_stack([cx, cy])
    k        = min(4, len(df))
    tree     = cKDTree(zone_xy)
    dists, idxs = tree.query(cell_xy, k=k)
    dists    = np.where(dists < 1, 1.0, dists)
    w        = 1.0 / dists**2
    w       /= w.sum(axis=1, keepdims=True)

    aqi_interp = (w * df["aqi_avg"].values[idxs]).sum(axis=1)
    # invert: higher score = cleaner air
    aqi_score  = 1.0 - _norm(aqi_interp)
    log.info("AQI score computed")
    return aqi_score


# ══════════════════════════════════════════════════════════════════════════════
# 9. CRIME PROXY SCORE  (inverted crime rate IDW)
# ══════════════════════════════════════════════════════════════════════════════
def compute_crime_score(cx, cy):
    log.info("Computing crime proxy score ...")
    df = pd.read_csv(C.PATHS["crime_csv"])

    dist_geo = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=C.CRS_GEO
    ).to_crs(C.CRS_METRIC)

    dist_xy  = np.column_stack([dist_geo.geometry.x, dist_geo.geometry.y])
    cell_xy  = np.column_stack([cx, cy])
    k        = min(4, len(df))
    tree     = cKDTree(dist_xy)
    dists, idxs = tree.query(cell_xy, k=k)
    dists    = np.where(dists < 1, 1.0, dists)
    w        = 1.0 / dists**2
    w       /= w.sum(axis=1, keepdims=True)

    crime_interp = (w * df["crime_rate_per_lakh"].values[idxs]).sum(axis=1)
    # invert: lower crime = higher score
    crime_score  = 1.0 - _norm(crime_interp)
    log.info("Crime proxy score computed")
    return crime_score


# ══════════════════════════════════════════════════════════════════════════════
# 10. GROWTH SCORE TARGET  (Fix 2: includes commercial bonus)
# ══════════════════════════════════════════════════════════════════════════════
def compute_growth_score(cx, cy, commercial_norm):
    log.info("Computing growth score target ...")
    df = pd.read_csv(C.PATHS["property_csv"])

    # 2-year CAGR 2021 -> 2023
    df["cagr"]         = (df["price_2023"] / df["price_2021"])**(1/2) - 1
    df["sale_density"] = df["sale_count"] / df["sale_count"].max()
    df["raw_score"]    = (C.GROWTH_SCORE_WEIGHTS["price_cagr"]   * df["cagr"] +
                          C.GROWTH_SCORE_WEIGHTS["sale_density"]  * df["sale_density"])

    ward_geo = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=C.CRS_GEO
    ).to_crs(C.CRS_METRIC)

    ward_xy  = np.column_stack([ward_geo.geometry.x, ward_geo.geometry.y])
    cell_xy  = np.column_stack([cx, cy])
    k        = C.IDW_NEIGHBOURS
    tree     = cKDTree(ward_xy)
    dists, idxs = tree.query(cell_xy, k=k)
    dists    = np.where(dists < 1, 1.0, dists)
    w        = 1.0 / dists**2
    w       /= w.sum(axis=1, keepdims=True)

    base_score = (w * df["raw_score"].values[idxs]).sum(axis=1)

    # Fix 2: commercial bonus — adds richness to sparse ward data
    commercial_bonus = 0.15 * commercial_norm
    final_score = base_score + commercial_bonus
    final_score = _norm(final_score)

    log.info(f"Growth score: mean={final_score.mean():.3f}, "
             f"std={final_score.std():.3f}, "
             f"IQR=[{np.percentile(final_score,25):.3f}, "
             f"{np.percentile(final_score,75):.3f}]")
    return final_score


# ══════════════════════════════════════════════════════════════════════════════
# 11. SPATIAL LAG  (Queen-contiguity weighted neighbourhood average)
# ══════════════════════════════════════════════════════════════════════════════
def compute_spatial_lag(local_matrix, cx, cy):
    log.info(f"Computing spatial lag features ({local_matrix.shape[1]} features) ...")
    t0      = time.time()
    cell_xy = np.column_stack([cx, cy])
    radius  = 2 * np.sqrt(2) * C.GRID_SIZE_M * 1.05
    alpha   = C.SPATIAL_LAG_ALPHA
    tree    = cKDTree(cell_xy)
    pairs   = tree.query_ball_point(cell_xy, r=radius)

    N, F    = local_matrix.shape
    lag_mat = np.zeros((N, F))

    for i, neighbours in enumerate(pairs):
        if not neighbours:
            lag_mat[i] = local_matrix[i]
            continue
        nb    = np.array(neighbours)
        diffs = cell_xy[nb] - cell_xy[i]
        dists = np.sqrt((diffs**2).sum(axis=1))
        dists = np.where(dists < 1, 1.0, dists)
        w     = np.exp(-alpha * dists)
        w    /= w.sum()
        lag_mat[i] = (w[:, None] * local_matrix[nb]).sum(axis=0)

        if i % 2000 == 0:
            log.info(f"  Spatial lag progress: {i:,}/{N:,} cells "
                     f"({100*i/N:.1f}%)")

    log.info(f"Spatial lag complete in {(time.time()-t0)/60:.1f} mins")
    return lag_mat


# ══════════════════════════════════════════════════════════════════════════════
# HELPER — normalise to [0, 1]
# ══════════════════════════════════════════════════════════════════════════════
def _norm(arr):
    mn, mx = arr.min(), arr.max()
    if mx - mn < 1e-9:
        return np.zeros_like(arr)
    return (arr - mn) / (mx - mn)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("=" * 55)
    log.info("IUD-NEPS  --  Step 3: Feature Engineering")
    log.info("=" * 55)
    overall_start = time.time()

    # ── Grid ──────────────────────────────────────────────────────────────────
    log.info("--- [1/5] Building Grid ---")
    grid = build_grid()
    cx   = grid["cx_m"].values
    cy   = grid["cy_m"].values
    N    = len(grid)

    # ── Potential features ────────────────────────────────────────────────────
    log.info("--- [2/5] Computing Potential Features ---")

    log.info("  [1/14] accessibility")
    accessibility = compute_accessibility(cx, cy)

    log.info("  [2/14] airport_proximity")
    airport_prox  = compute_airport_proximity(cx, cy)

    log.info("  [3/14] dmrc_proximity")
    dmrc_prox     = compute_dmrc_proximity(cx, cy)

    log.info("  [4/14] svc_education")
    svc_edu       = compute_service_density(cx, cy, "pois_education")

    log.info("  [5/14] svc_healthcare")
    svc_health    = compute_service_density(cx, cy, "pois_healthcare")

    log.info("  [6/14] svc_recreation")
    svc_rec       = compute_service_density(cx, cy, "pois_recreation")

    log.info("  [7/14] svc_civic")
    svc_civic     = compute_service_density(cx, cy, "pois_civic")

    log.info("  [8/14] svc_composite")
    svc_composite = np.column_stack([svc_edu, svc_health,
                                     svc_rec, svc_civic]).mean(axis=1)

    log.info("  [9/14] commercial")
    commercial    = compute_commercial(grid)

    log.info("  [10-14/14] demographics")
    demographics  = compute_demographics(cx, cy)

    # ── Assemble local potential matrix ───────────────────────────────────────
    local_potential_cols = {
        "accessibility":    accessibility,
        "airport_proximity":airport_prox,
        "dmrc_proximity":   dmrc_prox,
        "svc_education":    svc_edu,
        "svc_healthcare":   svc_health,
        "svc_recreation":   svc_rec,
        "svc_civic":        svc_civic,
        "svc_composite":    svc_composite,
        "commercial":       commercial,
        "pop_density":      demographics["pop_density"],
        "working_age_frac": demographics["working_age_frac"],
        "edu_index":        demographics["edu_index"],
        "median_income":    demographics["median_income"],
        "migration_rate":   demographics["migration_rate"],
    }
    local_names  = list(local_potential_cols.keys())
    local_mat    = np.column_stack(list(local_potential_cols.values()))

    # ── Spatial lag ───────────────────────────────────────────────────────────
    log.info("--- [3/5] Computing Spatial Lag ---")
    lag_mat   = compute_spatial_lag(local_mat, cx, cy)
    lag_names = [f"lag_{c}" for c in local_names]

    # ── Livability features ───────────────────────────────────────────────────
    log.info("--- [4/5] Computing Livability Features ---")

    log.info("  [1/7] aqi_score")
    aqi_score    = compute_aqi_score(cx, cy)

    log.info("  [2/7] parks_score")
    parks_score  = compute_service_density(cx, cy, "pois_parks")

    log.info("  [3/7] crime_proxy_score")
    crime_score  = compute_crime_score(cx, cy)

    livability_cols = {
        "aqi_score":        aqi_score,
        "parks_score":      parks_score,
        "healthcare_score": svc_health,
        "education_score":  svc_edu,
        "recreation_score": svc_rec,
        "civic_score":      svc_civic,
        "crime_proxy_score":crime_score,
    }

    # ── Growth score target ───────────────────────────────────────────────────
    log.info("--- [5/5] Computing Growth Score Target ---")
    growth_score = compute_growth_score(cx, cy, commercial)

    # ── Save potential features ───────────────────────────────────────────────
    all_potential_names = local_names + lag_names
    full_potential_mat  = np.hstack([local_mat, lag_mat])

    df_potential = pd.DataFrame(full_potential_mat, columns=all_potential_names)
    df_potential.insert(0, "cell_id", grid["cell_id"].values)
    df_potential["cx_lon"]      = grid["cx_lon"].values
    df_potential["cy_lat"]      = grid["cy_lat"].values
    df_potential["growth_score"]= growth_score
    df_potential.to_parquet(C.PATHS["potential_features"], index=False)

    # ── Save livability features ──────────────────────────────────────────────
    df_livability = pd.DataFrame(livability_cols)
    df_livability.insert(0, "cell_id", grid["cell_id"].values)
    df_livability["cx_lon"] = grid["cx_lon"].values
    df_livability["cy_lat"] = grid["cy_lat"].values

    # compute final livability score
    liv_score = sum(
        C.LIVABILITY_WEIGHTS[k.replace("_score", "")] * df_livability[k]
        for k in livability_cols.keys()
        if k.replace("_score", "") in C.LIVABILITY_WEIGHTS
    )
    df_livability["livability_score"] = _norm(liv_score.values)
    df_livability.to_parquet(C.PATHS["livability_features"], index=False)

    # ── Save feature column list ──────────────────────────────────────────────
    with open(C.PATHS["feature_cols"], "w") as f:
        json.dump({
            "potential": all_potential_names,
            "livability": list(livability_cols.keys())
        }, f, indent=2)

    elapsed = (time.time() - overall_start) / 60
    log.info("=" * 55)
    log.info(f"Feature engineering complete in {elapsed:.1f} mins")
    log.info(f"Potential features: {df_potential.shape[0]:,} cells x "
             f"{len(all_potential_names)} features")
    log.info(f"Livability features: {df_livability.shape[0]:,} cells x "
             f"{len(livability_cols)} features")
    log.info(f"Growth score range: [{growth_score.min():.3f}, "
             f"{growth_score.max():.3f}]")
    log.info("Next: py -3.12 scripts/train_models.py")
    log.info("=" * 55)