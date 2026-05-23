"""
dashboard/html_generator.py
Reads all JS/CSS templates and assembles the final self-contained HTML file.
"""

import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as C

TMPL = os.path.join(os.path.dirname(__file__), "templates")


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_html(geojson, shap_data, scenario_data, stats):
    css         = _read(os.path.join(TMPL, "css", "style.css"))
    js_map      = _read(os.path.join(TMPL, "js",  "map.js"))
    js_charts   = _read(os.path.join(TMPL, "js",  "charts.js"))
    js_panels   = _read(os.path.join(TMPL, "js",  "panels.js"))
    js_tabs     = _read(os.path.join(TMPL, "js",  "tabs.js"))

    sc_cfg = {
        k: {
            "label": v["label"].replace("\u2192", "->"),
            "color": v["color"],
            "type":  v.get("type", "metro"),
        }
        for k, v in C.SCENARIOS.items()
    }

    data_block = f"""
const GEOJSON   = {json.dumps(geojson)};
const SHAP      = {json.dumps(shap_data)};
const SCENARIOS = {json.dumps(scenario_data)};
const STATS     = {json.dumps(stats)};
const SC_CFG    = {json.dumps(sc_cfg)};
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IUD-NEPS | Delhi NCR Urban Analytics</title>
<script src="https://cdn.tailwindcss.com"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
{css}
</style>
</head>
<body class="h-screen flex flex-col overflow-hidden">

<!-- HEADER -->
<header class="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shrink-0 shadow-sm">
  <div class="flex items-center gap-3">
    <div class="w-8 h-8 bg-slate-900 rounded-lg flex items-center justify-center">
      <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"/>
      </svg>
    </div>
    <div>
      <h1 class="text-sm font-bold text-slate-900 leading-none">IUD-NEPS</h1>
      <p class="text-xs text-slate-500">Delhi NCR Urban Analytics</p>
    </div>
  </div>

  <nav class="flex gap-1 bg-slate-100 p-1 rounded-lg">
    <button onclick="switchTab('overview')"    id="tab-overview"
            class="tab-btn active px-4 py-1.5 rounded-md text-sm font-medium">
      Overview
    </button>
    <button onclick="switchTab('potential')"   id="tab-potential"
            class="tab-btn px-4 py-1.5 rounded-md text-sm font-medium text-slate-600">
      Potential
    </button>
    <button onclick="switchTab('livability')"  id="tab-livability"
            class="tab-btn px-4 py-1.5 rounded-md text-sm font-medium text-slate-600">
      Livability
    </button>
    <button onclick="switchTab('simulations')" id="tab-simulations"
            class="tab-btn px-4 py-1.5 rounded-md text-sm font-medium text-slate-600">
      Simulations
    </button>
  </nav>

  <div class="text-xs text-slate-400">11,651 grid cells &middot; 500m resolution</div>
</header>

<!-- MAIN -->
<main class="flex-1 flex overflow-hidden relative">

  <!-- Map -->
  <div class="flex-1 relative" id="map-container">
    <div id="map"></div>

    <!-- Basemap toggle — bottom right to avoid covering zoom -->
    <div class="absolute bottom-8 right-3 z-[1000] flex gap-1 bg-white rounded-lg shadow-md p-1">
      <button onclick="setBasemap('positron')"  id="bm-positron"
              class="basemap-btn active text-xs px-3 py-1.5 rounded-md font-medium">
        Map
      </button>
      <button onclick="setBasemap('satellite')" id="bm-satellite"
              class="basemap-btn text-xs px-3 py-1.5 rounded-md font-medium text-slate-600">
        Satellite
      </button>
    </div>

    <!-- Legend -->
    <div class="absolute bottom-8 left-3 z-[1000] bg-white rounded-xl shadow-md p-3 text-xs"
         id="map-legend">
      <p class="font-semibold text-slate-700 mb-2" id="legend-title">Trajectory</p>
      <div class="space-y-1.5" id="legend-items"></div>
    </div>

    <!-- Zoom hint -->
    <div id="zoom-hint"
         class="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] bg-white/90
                backdrop-blur-sm rounded-full px-4 py-1.5 text-xs text-slate-500
                shadow-sm pointer-events-none hidden">
      Zoom in to see property prices
    </div>
  </div>

  <!-- Right panel -->
  <div class="w-80 bg-white border-l border-slate-200 flex flex-col overflow-hidden shrink-0"
       id="right-panel">

    <!-- Overview -->
    <div id="panel-overview" class="flex-1 overflow-y-auto p-4 space-y-4">
      <div>
        <h2 class="text-sm font-bold text-slate-800 mb-3">Study Area Summary</h2>
        <div class="grid grid-cols-2 gap-2">
          <div class="stat-card bg-slate-50 rounded-xl p-3">
            <p class="text-2xl font-bold text-slate-900" id="s-total">-</p>
            <p class="text-xs text-slate-500 mt-0.5">Total Cells</p>
          </div>
          <div class="stat-card bg-green-50 rounded-xl p-3">
            <p class="text-2xl font-bold text-green-700" id="s-acc">-</p>
            <p class="text-xs text-green-600 mt-0.5">Accelerating</p>
          </div>
          <div class="stat-card bg-blue-50 rounded-xl p-3">
            <p class="text-2xl font-bold text-blue-700" id="s-emg">-</p>
            <p class="text-xs text-blue-600 mt-0.5">Emerging</p>
          </div>
          <div class="stat-card bg-slate-50 rounded-xl p-3">
            <p class="text-2xl font-bold text-slate-600" id="s-stb">-</p>
            <p class="text-xs text-slate-500 mt-0.5">Stable</p>
          </div>
          <div class="stat-card bg-red-50 rounded-xl p-3">
            <p class="text-2xl font-bold text-red-700" id="s-dec">-</p>
            <p class="text-xs text-red-600 mt-0.5">Declining</p>
          </div>
          <div class="stat-card bg-amber-50 rounded-xl p-3">
            <p class="text-2xl font-bold text-amber-700" id="s-uv">-</p>
            <p class="text-xs text-amber-600 mt-0.5">Undervalued</p>
          </div>
        </div>
      </div>

      <div>
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Average Scores
        </h3>
        <div class="space-y-2">
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-600 w-20">Potential</span>
            <div class="flex-1 bg-slate-100 rounded-full h-2">
              <div class="bg-blue-500 h-2 rounded-full transition-all" id="bar-pot"></div>
            </div>
            <span class="text-xs font-semibold text-slate-700 w-8 text-right" id="val-pot">-</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-600 w-20">Livability</span>
            <div class="flex-1 bg-slate-100 rounded-full h-2">
              <div class="bg-emerald-500 h-2 rounded-full transition-all" id="bar-liv"></div>
            </div>
            <span class="text-xs font-semibold text-slate-700 w-8 text-right" id="val-liv">-</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-600 w-20">Combined</span>
            <div class="flex-1 bg-slate-100 rounded-full h-2">
              <div class="bg-violet-500 h-2 rounded-full transition-all" id="bar-comb"></div>
            </div>
            <span class="text-xs font-semibold text-slate-700 w-8 text-right" id="val-comb">-</span>
          </div>
        </div>
      </div>

      <div>
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Trajectory Distribution
        </h3>
        <canvas id="traj-donut" height="160"></canvas>
      </div>
    </div>

    <!-- Potential -->
    <div id="panel-potential" class="flex-1 overflow-y-auto p-4 space-y-4 hidden">
      <h2 class="text-sm font-bold text-slate-800">Growth Potential</h2>
      <div>
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          SHAP Feature Importance
        </h3>
        <canvas id="shap-chart" height="280"></canvas>
      </div>
      <div class="bg-blue-50 rounded-xl p-3 text-xs text-blue-700">
        <p class="font-semibold mb-1">How to read</p>
        <p>Darker blue = higher growth potential. Zoom in past level 13 to see
           property prices. Click any cell for detailed analysis.</p>
      </div>
    </div>

    <!-- Livability -->
    <div id="panel-livability" class="flex-1 overflow-y-auto p-4 space-y-4 hidden">
      <h2 class="text-sm font-bold text-slate-800">Livability Score</h2>
      <div>
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Component Weights
        </h3>
        <canvas id="liv-chart" height="200"></canvas>
      </div>
      <div class="space-y-1" id="liv-quality"></div>
    </div>

    <!-- Simulations -->
    <div id="panel-simulations" class="flex-1 overflow-y-auto p-4 space-y-4 hidden">
      <h2 class="text-sm font-bold text-slate-800">Infrastructure Simulations</h2>
      <p class="text-xs text-slate-400 -mt-2">Click to select. Select multiple to combine.</p>
      <div class="space-y-1" id="sc-selector"></div>
      <div>
        <h3 class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Cells Reclassified per Scenario
        </h3>
        <canvas id="sc-chart" height="160"></canvas>
      </div>
      <div class="bg-amber-50 rounded-xl p-3 text-xs text-amber-700">
        <p class="font-semibold mb-1">About simulations</p>
        <p>Each scenario shows predicted growth impact if the infrastructure
           were built. Select a scenario to highlight affected cells on the map.</p>
      </div>
    </div>

  </div>

  <!-- Cell detail side panel -->
  <div id="side-panel"
       class="absolute top-0 right-80 h-full w-72 bg-white border-l border-slate-200
              shadow-xl z-[2000] flex flex-col overflow-hidden">
    <div class="flex items-center justify-between p-4 border-b border-slate-100 shrink-0">
      <h3 class="text-sm font-bold text-slate-800">Cell Analysis</h3>
      <button onclick="closePanel()"
              class="w-7 h-7 flex items-center justify-center rounded-lg
                     hover:bg-slate-100 text-slate-400 text-lg leading-none">
        &#x2715;
      </button>
    </div>
    <div class="flex-1 overflow-y-auto p-4" id="cell-detail"></div>
  </div>

</main>

<script>
{data_block}
</script>
<script>
{js_map}
</script>
<script>
{js_charts}
</script>
<script>
{js_panels}
</script>
<script>
{js_tabs}
</script>
<script>
window.addEventListener('load', () => {{
  window.currentTab = 'overview';
  console.log('IUD-NEPS init | SCENARIOS:', SCENARIOS.length, '| cells:', STATS.total_cells);
  initMap();
  renderStats();
  renderLegend('trajectory');
  renderDonut();
  renderShapChart();
  renderLivChart();
  renderLivQuality();
  renderScenarioSelector();
  renderScChart();
}});
</script>
</body>
</html>"""

    return html