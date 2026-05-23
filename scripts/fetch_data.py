"""
fetch_data.py  —  IUD-NEPS Step 2: Data Collection
===================================================
Extracts all data from local Geofabrik .osm.pbf file using osmium.
No API calls, no timeouts.

Place northern-zone-latest.osm.pbf in data/raw/ then run:
    py -3.12 scripts/fetch_data.py
"""

import os
import sys
import time
import logging
import warnings
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
import osmium

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
        logging.FileHandler(os.path.join(C.BASE_DIR, "fetch_data.log"), mode="w"),
    ]
)
log = logging.getLogger("iud-neps")

PBF_PATH = os.path.join(C.BASE_DIR, "data", "raw", "northern-zone-260520.osm.pbf")

# ══════════════════════════════════════════════════════════════════════════════
# BBOX FILTER  — only keep nodes within Delhi NCR bounds
# ══════════════════════════════════════════════════════════════════════════════
def in_bbox(lat, lon):
    return (C.BBOX["south"] <= lat <= C.BBOX["north"] and
            C.BBOX["west"]  <= lon <= C.BBOX["east"])


# ══════════════════════════════════════════════════════════════════════════════
# OSM HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

# ── POI Handler ───────────────────────────────────────────────────────────────
class POIHandler(osmium.SimpleHandler):
    """
    Extracts nodes and way centroids matching given OSM tags.
    tag_filters: dict of {key: list_of_values or True}
    """
    def __init__(self, tag_filters):
        super().__init__()
        self.tag_filters = tag_filters
        self.points = []

    def _matches(self, tags):
        for key, values in self.tag_filters.items():
            if key in tags:
                if values is True:
                    return True
                if tags[key] in values:
                    return True
        return False

    def node(self, n):
        if not in_bbox(n.location.lat, n.location.lon):
            return
        if self._matches(n.tags):
            self.points.append(Point(n.location.lon, n.location.lat))

    def area(self, a):
        # get centroid of way/relation areas
        try:
            loc = a.original_geometry().centroid()
            if in_bbox(loc.y, loc.x) and self._matches(a.tags):
                self.points.append(Point(loc.x, loc.y))
        except Exception:
            pass

    def to_geodataframe(self):
        if not self.points:
            return gpd.GeoDataFrame(geometry=[], crs=C.CRS_GEO)
        return gpd.GeoDataFrame(geometry=self.points, crs=C.CRS_GEO)


# ── Road Handler ──────────────────────────────────────────────────────────────
class RoadHandler(osmium.SimpleHandler):
    """Extracts drive_service roads as linestrings."""
    ROAD_TYPES = {
        "motorway", "trunk", "primary", "secondary", "tertiary",
        "unclassified", "residential", "service",
        "motorway_link", "trunk_link", "primary_link",
        "secondary_link", "tertiary_link",
    }

    def __init__(self):
        super().__init__()
        self.roads = []
        self._node_coords = {}

    def node(self, n):
        if in_bbox(n.location.lat, n.location.lon):
            self._node_coords[n.id] = (n.location.lon, n.location.lat)

    def way(self, w):
        if "highway" not in w.tags:
            return
        if w.tags["highway"] not in self.ROAD_TYPES:
            return
        coords = []
        for node_ref in w.nodes:
            if node_ref.ref in self._node_coords:
                coords.append(self._node_coords[node_ref.ref])
        if len(coords) >= 2:
            # check at least one node is in bbox
            lats = [c[1] for c in coords]
            lons = [c[0] for c in coords]
            if (C.BBOX["south"] <= min(lats) <= C.BBOX["north"] or
                C.BBOX["south"] <= max(lats) <= C.BBOX["north"]):
                self.roads.append({
                    "highway": w.tags.get("highway"),
                    "name":    w.tags.get("name", ""),
                    "oneway":  w.tags.get("oneway", "no"),
                    "maxspeed":w.tags.get("maxspeed", ""),
                    "geometry": LineString(coords)
                })

    def to_geodataframe(self):
        if not self.roads:
            return gpd.GeoDataFrame(geometry=[], crs=C.CRS_GEO)
        return gpd.GeoDataFrame(self.roads, crs=C.CRS_GEO)


# ══════════════════════════════════════════════════════════════════════════════
# POI DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════
POI_DEFINITIONS = {
    "pois_education":  {"amenity": ["school", "college", "university", "library"]},
    "pois_healthcare": {"amenity": ["hospital", "clinic", "pharmacy", "doctors"]},
    "pois_recreation": {"leisure": ["sports_centre", "playground", "fitness_centre"],
                        "amenity": ["cinema", "theatre"]},
    "pois_civic":      {"amenity": ["police", "post_office", "fire_station",
                                    "community_centre", "courthouse"]},
    "pois_commercial": {"shop": True,
                        "amenity": ["marketplace", "bank", "restaurant",
                                    "cafe", "fast_food"]},
    "pois_parks":      {"leisure": ["park", "nature_reserve", "garden"]},
}


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def extract_pois():
    total = len(POI_DEFINITIONS)
    for i, (key, tag_filters) in enumerate(POI_DEFINITIONS.items(), 1):
        path = C.PATHS[key]
        if os.path.exists(path):
            log.info(f"[{i}/{total}] {key} already exists — skipping.")
            continue

        log.info(f"[{i}/{total}] Extracting {key} from .pbf ...")
        t0 = time.time()

        handler = POIHandler(tag_filters)
        handler.apply_file(PBF_PATH, locations=True)
        gdf = handler.to_geodataframe()
        gdf.to_file(path, driver="GeoJSON")

        elapsed = time.time() - t0
        log.info(f"[{i}/{total}] {key}: {len(gdf):,} features in {elapsed:.1f}s ✓")


def extract_roads():
    path = C.PATHS["road_graph"]  # we'll save as geojson instead
    road_path = os.path.join(C.BASE_DIR, "data", "raw", "roads.geojson")

    if os.path.exists(road_path):
        log.info("Roads already extracted — skipping.")
        return

    log.info("Extracting road network from .pbf ...")
    log.info("This may take 5–10 mins ...")
    t0 = time.time()

    handler = RoadHandler()
    handler.apply_file(PBF_PATH, locations=True)
    gdf = handler.to_geodataframe()
    gdf.to_file(road_path, driver="GeoJSON")

    elapsed = (time.time() - t0) / 60
    size_mb = os.path.getsize(road_path) / 1e6
    log.info(f"Roads extracted: {len(gdf):,} segments, {size_mb:.1f} MB in {elapsed:.1f} mins ✓")


# ══════════════════════════════════════════════════════════════════════════════
# CSV SEEDS
# ══════════════════════════════════════════════════════════════════════════════
PROPERTY_DATA = [
    ("Connaught Place",         28.6315, 77.2167, 22000, 23500, 27000, 420),
    ("Karol Bagh",              28.6530, 77.1900, 14500, 15200, 17800, 580),
    ("Lajpat Nagar",            28.5700, 77.2430, 11000, 11800, 14200, 610),
    ("Saket",                   28.5245, 77.2066, 13500, 14100, 16500, 390),
    ("Dwarka Sector 21",        28.5521, 77.0588,  7500,  8000,  9800, 730),
    ("Dwarka Sector 10",        28.5820, 77.0540,  7200,  7700,  9200, 680),
    ("Rohini Sector 3",         28.7350, 77.1200,  6800,  7100,  8400, 510),
    ("Pitampura",               28.7010, 77.1310,  7100,  7500,  9000, 470),
    ("Noida Sector 18",         28.5700, 77.3200,  8500,  9100, 11200, 820),
    ("Noida Sector 62",         28.6270, 77.3730,  5500,  5900,  7400, 690),
    ("Gurgaon Cyber City",      28.4950, 77.0880, 12000, 12800, 15600, 920),
    ("Gurgaon Sohna Road",      28.4500, 77.0400,  6500,  7000,  8800, 740),
    ("Ghaziabad Raj Nagar",     28.6620, 77.4220,  4500,  4800,  6100, 610),
    ("Ghaziabad Vaishali",      28.6450, 77.3500,  5200,  5600,  7000, 550),
    ("Sarita Vihar",            28.5320, 77.2900,  9500, 10200, 12400, 430),
    ("Hazrat Nizamuddin",       28.5885, 77.2510, 10500, 11100, 13500, 380),
    ("Vasant Kunj",             28.5200, 77.1500, 14000, 14800, 17200, 360),
    ("Janakpuri",               28.6270, 77.0820,  7800,  8300, 10100, 490),
    ("Uttam Nagar",             28.6200, 77.0500,  5500,  5900,  7300, 620),
    ("Shahdara",                28.6720, 77.2880,  6000,  6400,  7900, 530),
    ("Preet Vihar",             28.6430, 77.2950,  7200,  7700,  9400, 490),
    ("Mayur Vihar",             28.6075, 77.2950,  8500,  9000, 11000, 510),
    ("Okhla",                   28.5400, 77.2600,  7000,  7500,  9100, 460),
    ("Burari",                  28.7480, 77.2070,  4200,  4500,  5700, 420),
    ("Narela",                  28.8400, 77.0900,  3100,  3300,  4200, 310),
    ("Najafgarh",               28.6080, 76.9790,  3500,  3700,  4700, 280),
    ("Palam",                   28.5900, 77.0870,  5800,  6200,  7700, 450),
    ("Mehrauli",                28.5200, 77.1860,  8000,  8500, 10300, 350),
    ("Sangam Vihar",            28.5050, 77.2500,  5200,  5600,  7000, 580),
    ("Tughlakabad",             28.4850, 77.2570,  4800,  5100,  6400, 390),
    ("Badarpur",                28.5000, 77.3000,  4500,  4800,  6000, 420),
    ("Faridabad Sector 15",     28.4020, 77.3190,  4200,  4500,  5700, 390),
    ("Faridabad NIT",           28.3820, 77.3080,  3900,  4200,  5300, 360),
    ("Manesar",                 28.3580, 76.9380,  4800,  5200,  6600, 480),
    ("Sohna",                   28.2460, 77.0720,  2800,  3000,  3900, 210),
]

CENSUS_DATA = [
    ("Connaught Place",         28.6315, 77.2167, 28500, 0.72, 0.85, 85000, 0.18),
    ("Karol Bagh",              28.6530, 77.1900, 32000, 0.68, 0.78, 62000, 0.22),
    ("Lajpat Nagar",            28.5700, 77.2430, 24000, 0.70, 0.80, 72000, 0.20),
    ("Saket",                   28.5245, 77.2066, 18000, 0.71, 0.83, 78000, 0.16),
    ("Dwarka Sector 21",        28.5521, 77.0588, 22000, 0.73, 0.76, 58000, 0.31),
    ("Dwarka Sector 10",        28.5820, 77.0540, 25000, 0.72, 0.75, 56000, 0.29),
    ("Rohini Sector 3",         28.7350, 77.1200, 26000, 0.69, 0.74, 52000, 0.28),
    ("Pitampura",               28.7010, 77.1310, 24000, 0.70, 0.75, 54000, 0.26),
    ("Noida Sector 18",         28.5700, 77.3200, 20000, 0.76, 0.82, 68000, 0.38),
    ("Noida Sector 62",         28.6270, 77.3730, 15000, 0.77, 0.80, 62000, 0.42),
    ("Gurgaon Cyber City",      28.4950, 77.0880, 12000, 0.78, 0.88, 95000, 0.45),
    ("Gurgaon Sohna Road",      28.4500, 77.0400,  8000, 0.76, 0.79, 64000, 0.40),
    ("Ghaziabad Raj Nagar",     28.6620, 77.4220, 18000, 0.71, 0.72, 48000, 0.35),
    ("Ghaziabad Vaishali",      28.6450, 77.3500, 22000, 0.73, 0.74, 50000, 0.38),
    ("Sarita Vihar",            28.5320, 77.2900, 19000, 0.72, 0.79, 65000, 0.25),
    ("Hazrat Nizamuddin",       28.5885, 77.2510, 35000, 0.65, 0.71, 48000, 0.19),
    ("Vasant Kunj",             28.5200, 77.1500, 14000, 0.72, 0.84, 82000, 0.17),
    ("Janakpuri",               28.6270, 77.0820, 22000, 0.70, 0.77, 58000, 0.24),
    ("Uttam Nagar",             28.6200, 77.0500, 28000, 0.68, 0.70, 44000, 0.30),
    ("Shahdara",                28.6720, 77.2880, 30000, 0.67, 0.69, 42000, 0.27),
    ("Preet Vihar",             28.6430, 77.2950, 26000, 0.70, 0.74, 52000, 0.29),
    ("Mayur Vihar",             28.6075, 77.2950, 24000, 0.71, 0.76, 56000, 0.28),
    ("Okhla",                   28.5400, 77.2600, 32000, 0.66, 0.68, 38000, 0.23),
    ("Burari",                  28.7480, 77.2070, 20000, 0.67, 0.66, 36000, 0.26),
    ("Narela",                  28.8400, 77.0900,  8000, 0.65, 0.62, 28000, 0.22),
    ("Najafgarh",               28.6080, 76.9790,  5000, 0.64, 0.60, 26000, 0.18),
    ("Palam",                   28.5900, 77.0870, 22000, 0.69, 0.72, 46000, 0.28),
    ("Mehrauli",                28.5200, 77.1860, 26000, 0.67, 0.70, 44000, 0.21),
    ("Sangam Vihar",            28.5050, 77.2500, 38000, 0.65, 0.64, 32000, 0.24),
    ("Tughlakabad",             28.4850, 77.2570, 18000, 0.66, 0.65, 34000, 0.22),
    ("Badarpur",                28.5000, 77.3000, 24000, 0.67, 0.66, 36000, 0.25),
    ("Faridabad Sector 15",     28.4020, 77.3190, 16000, 0.70, 0.72, 46000, 0.32),
    ("Faridabad NIT",           28.3820, 77.3080, 22000, 0.68, 0.70, 42000, 0.30),
    ("Manesar",                 28.3580, 76.9380,  4000, 0.75, 0.74, 52000, 0.44),
    ("Sohna",                   28.2460, 77.0720,  2000, 0.66, 0.62, 28000, 0.20),
]

AQI_DATA = [
    ("Anand Vihar",             28.6469, 77.3152, 312, 298, 285),
    ("Punjabi Bagh",            28.6730, 77.1310, 278, 265, 254),
    ("RK Puram",                28.5650, 77.1870, 245, 238, 229),
    ("Dwarka Sector 8",         28.5733, 77.0714, 231, 225, 218),
    ("IGI Airport",             28.5562, 77.1000, 198, 192, 185),
    ("Noida Sector 62",         28.6270, 77.3730, 265, 252, 241),
    ("Noida Sector 125",        28.5355, 77.3910, 248, 236, 226),
    ("Gurgaon Vikas Sadan",     28.4520, 77.0260, 218, 208, 199),
    ("Gurgaon Teri Gram",       28.4280, 77.0120, 205, 196, 188),
    ("Faridabad Sector 16A",    28.4082, 77.3170, 289, 275, 263),
    ("Ghaziabad Loni",          28.7480, 77.2880, 334, 318, 304),
    ("Ghaziabad Vasundhara",    28.6450, 77.3500, 295, 281, 269),
    ("Narela",                  28.8400, 77.0900, 268, 255, 244),
    ("Rohini",                  28.7350, 77.1200, 258, 246, 236),
    ("Shahdara",                28.6720, 77.2880, 302, 288, 276),
    ("Okhla Phase 2",           28.5300, 77.2700, 252, 240, 230),
    ("Manesar",                 28.3580, 76.9380, 188, 180, 173),
    ("Sohna",                   28.2460, 77.0720, 165, 158, 152),
    ("Mehrauli",                28.5200, 77.1860, 238, 227, 218),
    ("Burari",                  28.7480, 77.2070, 271, 258, 247),
]

CRIME_DATA = [
    ("Central Delhi",           28.6448, 77.2167, 842, 18),
    ("North Delhi",             28.7200, 77.2000, 612, 22),
    ("North East Delhi",        28.6900, 77.3000, 754, 16),
    ("North West Delhi",        28.7100, 77.1200, 534, 28),
    ("West Delhi",              28.6500, 77.0800, 498, 24),
    ("South West Delhi",        28.5800, 77.0700, 445, 20),
    ("South Delhi",             28.5200, 77.2100, 389, 26),
    ("South East Delhi",        28.5400, 77.2800, 412, 18),
    ("East Delhi",              28.6300, 77.3000, 578, 20),
    ("New Delhi",               28.6139, 77.2090, 318, 12),
    ("Dwarka",                  28.5921, 77.0460, 356, 14),
    ("Outer Delhi",             28.7800, 77.1100, 467, 30),
    ("Outer North Delhi",       28.8200, 77.0800, 398, 22),
    ("Rohini",                  28.7350, 77.1200, 423, 18),
    ("Noida",                   28.5700, 77.3200, 345, 24),
    ("Gurgaon",                 28.4595, 77.0266, 298, 28),
    ("Faridabad",               28.4089, 77.3178, 512, 26),
    ("Ghaziabad",               28.6692, 77.4538, 489, 30),
]

def seed_csvs():
    datasets = [
        (C.PATHS["property_csv"], PROPERTY_DATA,
         ["ward","lat","lon","price_2019","price_2021","price_2023","sale_count"],
         "Property prices"),
        (C.PATHS["census_csv"], CENSUS_DATA,
         ["ward","lat","lon","pop_density","working_age_frac","edu_index","median_income","migration_rate"],
         "Census"),
        (C.PATHS["aqi_csv"], AQI_DATA,
         ["zone","lat","lon","aqi_2021","aqi_2022","aqi_2023"],
         "AQI"),
        (C.PATHS["crime_csv"], CRIME_DATA,
         ["district","lat","lon","crime_rate_per_lakh","police_stations"],
         "Crime proxy"),
    ]
    for path, data, cols, label in datasets:
        if os.path.exists(path):
            log.info(f"{label} CSV already exists — skipping.")
            continue
        pd.DataFrame(data, columns=cols).to_csv(path, index=False)
        log.info(f"{label} CSV seeded — {len(data)} rows ✓")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log.info("=" * 55)
    log.info("IUD-NEPS  —  Step 2: Data Collection")
    log.info("=" * 55)

    if not os.path.exists(PBF_PATH):
        log.error(f"PBF file not found at: {PBF_PATH}")
        log.error("Download northern-zone-latest.osm.pbf from geofabrik.de and place in data/raw/")
        sys.exit(1)

    log.info(f"PBF file found: {os.path.getsize(PBF_PATH)/1e6:.1f} MB")
    overall_start = time.time()

    log.info("--- [1/3] Extracting POIs ---")
    extract_pois()

    log.info("--- [2/3] Extracting Roads ---")
    if C.USE_ROAD_NETWORK:
        extract_roads()
    else:
        log.info("USE_ROAD_NETWORK=False — skipping roads. Using Euclidean fallback.")

    log.info("--- [3/3] Seeding CSVs ---")
    seed_csvs()

    elapsed = (time.time() - overall_start) / 60
    log.info("=" * 55)
    log.info(f"Data collection complete in {elapsed:.1f} mins")
    log.info("Next: py -3.12 scripts/feature_engineering.py")
    log.info("=" * 55)