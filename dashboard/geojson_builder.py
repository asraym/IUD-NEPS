"""
dashboard/geojson_builder.py
Converts the merged dataframe into GeoJSON for Leaflet.
"""

import geopandas as gpd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C


def r(v, d=3):
    return round(float(v), d)


def build_geojson(df, log):
    log.info("Building GeoJSON ...")
    grid = gpd.read_file(C.PATHS["grid_geojson"])

    # convert to WGS84 — Leaflet requires lat/lon coordinates
    if grid.crs and grid.crs.to_epsg() != 4326:
        log.info(f"  Converting grid from {grid.crs} to WGS84 ...")
        grid = grid.to_crs(C.CRS_GEO)

    features = []
    for _, row in df.iterrows():
        geom = grid[grid["cell_id"] == row["cell_id"]].geometry.values
        if len(geom) == 0:
            continue

        # scenario boosts
        scenarios = {
            k: r(row[f"boost_{k}"], 4)
            for k in C.SCENARIOS
            if f"boost_{k}" in df.columns
        }

        props = {
            # identity
            "id":            int(row["cell_id"]),
            "lat":           r(row["cy_lat"], 4),
            "lon":           r(row["cx_lon"], 4),
            # scores
            "trajectory":    row["trajectory"],
            "potential":     r(row["predicted_growth"]),
            "livability":    r(row["livability_score"]),
            "combined":      r(row["combined_score"]),
            "growth_score":  r(row["growth_score"]),
            "delta_g":       r(row["delta_G"]),
            # real estate
            "ward":          row["ward_name"],
            "price_2023":    int(row["price_2023"]),
            "price_2021":    int(row["price_2021"]),
            "price_cagr":    r(row["price_cagr"], 2),
            "ward_dist_km":  r(row["ward_dist_km"], 2),
            "valuation":     row["valuation"],
            # potential features
            "accessibility": r(row["accessibility"]),
            "airport_prox":  r(row["airport_proximity"]),
            "dmrc_prox":     r(row["dmrc_proximity"]),
            "commercial":    r(row["commercial"]),
            "migration_rate":r(row["migration_rate"]),
            # livability features
            "aqi_score":     r(row["aqi_score"]),
            "parks_score":   r(row["parks_score"]),
            "crime_score":   r(row["crime_proxy_score"]),
            # scenarios
            **{f"sc_{k}": v for k, v in scenarios.items()},
        }

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [list(geom[0].exterior.coords)],
            },
            "properties": props,
        })

    log.info(f"GeoJSON built: {len(features):,} features")
    return {"type": "FeatureCollection", "features": features}