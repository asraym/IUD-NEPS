// map.js — Leaflet map initialisation, layer rendering, price labels

let map, geojsonLayer, baseLayers = {};
let priceLabels       = [];
let currentBasemap    = 'positron';
let selectedScenarios = new Set();   // multi-select support

const TRAJ_COLORS = {
  Accelerating: '#16a34a',
  Emerging:     '#2563eb',
  Stable:       '#94a3b8',
  Declining:    '#dc2626',
};

function initMap() {
  map = L.map('map', { center: [28.64, 77.15], zoom: 11, zoomControl: true });

  baseLayers.positron = L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    { attribution: '&copy; OpenStreetMap &copy; CartoDB', maxZoom: 19 }
  ).addTo(map);

  baseLayers.satellite = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { attribution: '&copy; Esri', maxZoom: 19 }
  );

  renderGeojson('trajectory');
  map.on('zoomend', handleZoom);
  map.on('moveend', updatePriceLabels);
}

function setBasemap(name) {
  if (currentBasemap === name) return;
  Object.values(baseLayers).forEach(l => map.removeLayer(l));
  baseLayers[name].addTo(map);
  baseLayers[name].bringToBack();
  if (geojsonLayer) geojsonLayer.bringToFront();
  currentBasemap = name;
  document.getElementById('bm-positron').classList.toggle('active', name === 'positron');
  document.getElementById('bm-satellite').classList.toggle('active', name === 'satellite');
}

// ── Color helpers ──────────────────────────────────────────────────────────
function scoreColor(val, low, high) {
  const t  = Math.max(0, Math.min(1, val));
  const r1 = parseInt(low.slice(1,3),16),  g1 = parseInt(low.slice(3,5),16),  b1 = parseInt(low.slice(5,7),16);
  const r2 = parseInt(high.slice(1,3),16), g2 = parseInt(high.slice(3,5),16), b2 = parseInt(high.slice(5,7),16);
  return `rgb(${Math.round(r1+(r2-r1)*t)},${Math.round(g1+(g2-g1)*t)},${Math.round(b1+(b2-b1)*t)})`;
}

function blendWithWhite(hex, intensity) {
  // blend a hex color with white based on intensity [0-1]
  const t  = Math.max(0, Math.min(1, intensity));
  const r  = parseInt(hex.slice(1,3),16);
  const g  = parseInt(hex.slice(3,5),16);
  const b  = parseInt(hex.slice(5,7),16);
  return `rgb(${Math.round(255+(r-255)*t)},${Math.round(255+(g-255)*t)},${Math.round(255+(b-255)*t)})`;
}

function cellColor(p, mode) {
  if (mode === 'trajectory')  return TRAJ_COLORS[p.trajectory] || '#94a3b8';
  if (mode === 'potential')   return scoreColor(p.potential,  '#bfdbfe', '#1d4ed8');
  if (mode === 'livability')  return scoreColor(p.livability, '#bbf7d0', '#15803d');
  if (mode === 'combined')    return scoreColor(p.combined,   '#ddd6fe', '#4c1d95');

  if (mode === 'scenario') {
    if (selectedScenarios.size === 0) return '#f1f5f9';
    // sum boosts from all selected scenarios
    let totalBoost = 0;
    selectedScenarios.forEach(key => { totalBoost += p['sc_' + key] || 0; });
    totalBoost = Math.min(totalBoost, 1);
    if (totalBoost < 0.01) return '#f1f5f9';
    // color by dominant scenario
    let maxKey = null, maxVal = 0;
    selectedScenarios.forEach(key => {
      const v = p['sc_' + key] || 0;
      if (v > maxVal) { maxVal = v; maxKey = key; }
    });
    const baseColor = (maxKey && SC_CFG[maxKey]) ? SC_CFG[maxKey].color : '#f97316';
    return blendWithWhite(baseColor, Math.min(totalBoost * 3, 1));
  }
  return '#94a3b8';
}

function renderGeojson(mode) {
  if (geojsonLayer) map.removeLayer(geojsonLayer);
  clearPriceLabels();

  geojsonLayer = L.geoJSON(GEOJSON, {
    style: f => ({
      fillColor:   cellColor(f.properties, mode),
      fillOpacity: 0.55,
      color:       'rgba(0,0,0,0.06)',
      weight:      0.4,
    }),
    onEachFeature: (f, layer) => {
      layer.on('click',     () => showCellDetail(f.properties));
      layer.on('mouseover', function() { this.setStyle({ fillOpacity: 0.85, weight: 1, color: '#1e293b' }); });
      layer.on('mouseout',  function() { this.setStyle({ fillOpacity: 0.55, weight: 0.4, color: 'rgba(0,0,0,0.06)' }); });
    },
  }).addTo(map);

  geojsonLayer.bringToFront();
  handleZoom();
}

// ── Price labels ───────────────────────────────────────────────────────────
function handleZoom() {
  const z    = map.getZoom();
  const hint = document.getElementById('zoom-hint');
  if (window.currentTab === 'potential') {
    if (z < 13) { hint.classList.remove('hidden'); clearPriceLabels(); }
    else        { hint.classList.add('hidden');    updatePriceLabels(); }
  } else {
    hint.classList.add('hidden');
    clearPriceLabels();
  }
}

function updatePriceLabels() {
  if (window.currentTab !== 'potential' || map.getZoom() < 13) return;
  clearPriceLabels();
  const bounds = map.getBounds();
  const shown  = {};

  GEOJSON.features.forEach(f => {
    const p = f.properties;
    if (!bounds.contains([p.lat, p.lon])) return;
    if (shown[p.ward]) return;
    shown[p.ward] = true;

    const icon = L.divIcon({
      className: '',
      html: `<div class="price-label">Rs.${(p.price_2023/1000).toFixed(0)}k/sqft</div>`,
      iconAnchor: [0, 0],
    });
    priceLabels.push(L.marker([p.lat, p.lon], { icon, interactive: false }).addTo(map));
  });
}

function clearPriceLabels() {
  priceLabels.forEach(m => map.removeLayer(m));
  priceLabels = [];
}