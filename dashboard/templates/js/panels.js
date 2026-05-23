// panels.js — cell detail side panel, stats panel, livability quality badges

function renderStats() {
  document.getElementById('s-total').textContent = STATS.total_cells.toLocaleString();
  document.getElementById('s-acc').textContent   = STATS.accelerating.toLocaleString();
  document.getElementById('s-emg').textContent   = STATS.emerging.toLocaleString();
  document.getElementById('s-stb').textContent   = STATS.stable.toLocaleString();
  document.getElementById('s-dec').textContent   = STATS.declining.toLocaleString();
  document.getElementById('s-uv').textContent    = STATS.undervalued.toLocaleString();

  [
    ['bar-pot',  'val-pot',  STATS.avg_potential],
    ['bar-liv',  'val-liv',  STATS.avg_livability],
    ['bar-comb', 'val-comb', STATS.avg_combined],
  ].forEach(([bid, vid, v]) => {
    document.getElementById(bid).style.width     = (v * 100) + '%';
    document.getElementById(vid).textContent     = v.toFixed(2);
  });
}

function renderLivQuality() {
  const quality = {
    'AQI':          { q: 'Estimated', note: '20 monitoring zones, IDW interpolated' },
    'Healthcare':   { q: 'Good',      note: '1,693 OSM POIs' },
    'Education':    { q: 'Good',      note: '361 OSM POIs' },
    'Parks':        { q: 'Weak',      note: '114 OSM POIs — undertagged in India' },
    'Recreation':   { q: 'Moderate',  note: '329 OSM POIs' },
    'Civic':        { q: 'Moderate',  note: '282 OSM POIs' },
    'Crime Safety': { q: 'Estimated', note: 'District-level proxy data' },
  };
  const colors = {
    'Good':      'bg-green-100 text-green-700',
    'Moderate':  'bg-amber-100 text-amber-700',
    'Weak':      'bg-red-100 text-red-700',
    'Estimated': 'bg-slate-100 text-slate-600',
  };
  document.getElementById('liv-quality').innerHTML =
    Object.entries(quality).map(([k, v], i, arr) => `
      <div class="flex items-start justify-between gap-2">
        <div>
          <p class="text-xs font-medium text-slate-700">${k}</p>
          <p class="text-xs text-slate-400">${v.note}</p>
        </div>
        <span class="text-xs px-2 py-0.5 rounded-full shrink-0 ${colors[v.q]}">${v.q}</span>
      </div>
      ${i < arr.length - 1 ? '<div class="border-t border-slate-100 my-1"></div>' : ''}
    `).join('');
}

function renderScenarioSelector() {
  document.getElementById('sc-selector').innerHTML = SCENARIOS.map(s => `
    <div onclick="selectScenario('${s.key}')"
         id="sc-btn-${s.key}"
         style="border: 1.5px solid #e2e8f0;
                border-radius: 10px;
                padding: 10px 14px;
                cursor: pointer;
                margin-bottom: 8px;
                background: white;
                box-shadow: 0 1px 4px rgba(0,0,0,0.08);
                user-select: none;">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <div style="width:12px; height:12px; border-radius:50%;
                      background:${s.color}; flex-shrink:0;
                      box-shadow: 0 0 0 3px ${s.color}22;"></div>
          <span style="font-weight:600; font-size:12px; color:#0f172a; line-height:1.3;">
            ${s.label.replace('->', '\u2192')}
          </span>
        </div>
        <div id="sc-check-${s.key}"
             style="width:18px; height:18px; border-radius:50%;
                    border: 1.5px solid #cbd5e1;
                    display:flex; align-items:center; justify-content:center;
                    flex-shrink:0; font-size:10px; color:white;">
        </div>
      </div>
      <div style="display:flex; gap:16px; margin-left:20px; font-size:11px; color:#64748b;">
        <span><b style="color:#334155">${s.affected.toLocaleString()}</b> cells</span>
        <span><b style="color:#334155">${(s.max_impact * 100).toFixed(1)}%</b> max</span>
        <span><b style="color:#334155">${s.reclassified.toLocaleString()}</b> reclassified</span>
      </div>
    </div>
  `).join('');
}

function selectScenario(key) {
  if (selectedScenarios.has(key)) {
    selectedScenarios.delete(key);
  } else {
    selectedScenarios.add(key);
  }

  SCENARIOS.forEach(s => {
    const btn   = document.getElementById('sc-btn-' + s.key);
    const check = document.getElementById('sc-check-' + s.key);
    const color = SC_CFG[s.key]?.color || '#1e293b';

    if (selectedScenarios.has(s.key)) {
      btn.style.borderColor   = color;
      btn.style.borderWidth   = '2px';
      btn.style.background    = color + '08';
      btn.style.boxShadow     = `0 0 0 3px ${color}22`;
      check.style.background  = color;
      check.style.borderColor = color;
      check.innerHTML         = '&#10003;';
    } else {
      btn.style.borderColor   = '#e2e8f0';
      btn.style.borderWidth   = '1.5px';
      btn.style.background    = 'white';
      btn.style.boxShadow     = '0 1px 4px rgba(0,0,0,0.08)';
      check.style.background  = 'transparent';
      check.style.borderColor = '#cbd5e1';
      check.innerHTML         = '';
    }
  });

  renderGeojson('scenario');
  renderLegend('scenario');
}

// ── Cell detail ────────────────────────────────────────────────────────────
function showCellDetail(p) {
  const trajColor = {
    Accelerating: 'text-green-700 bg-green-50',
    Emerging:     'text-blue-700 bg-blue-50',
    Stable:       'text-slate-600 bg-slate-100',
    Declining:    'text-red-700 bg-red-50',
  }[p.trajectory] || '';

  const valColor = {
    'Undervalued':   'text-emerald-700 bg-emerald-50',
    'Overvalued':    'text-rose-700 bg-rose-50',
    'Fairly Valued': 'text-blue-700 bg-blue-50',
  }[p.valuation] || '';

  document.getElementById('cell-detail').innerHTML = `
    <div class="space-y-3">

      <div class="bg-slate-50 rounded-xl p-3">
        <p class="text-xs text-slate-500 mb-1">Location</p>
        <p class="text-xs font-mono text-slate-700">${p.lat.toFixed(4)}N, ${p.lon.toFixed(4)}E</p>
        <p class="text-xs text-slate-400 mt-0.5">Cell ID: ${p.id}</p>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-xs text-slate-600">Trajectory</span>
        <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${trajColor}">
          ${p.trajectory}
        </span>
      </div>

      <div>
        <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Scores</p>
        ${scoreBar('Growth Potential', p.potential,  '#3b82f6')}
        ${scoreBar('Livability',       p.livability, '#10b981')}
        ${scoreBar('Combined',         p.combined,   '#8b5cf6')}
      </div>

      <div class="bg-amber-50 rounded-xl p-3">
        <p class="text-xs font-semibold text-amber-800 mb-2">Real Estate</p>
        <p class="text-xs text-amber-700 mb-2">
          Nearest ward: <span class="font-semibold">${p.ward}</span>
          <span class="text-amber-400 ml-1">(${p.ward_dist_km} km away)</span>
        </p>
        <div class="grid grid-cols-2 gap-2">
          <div class="bg-white rounded-lg p-2">
            <p class="text-base font-bold text-slate-800">Rs.${(p.price_2023/1000).toFixed(1)}k</p>
            <p class="text-xs text-slate-500">per sqft (2023)</p>
          </div>
          <div class="bg-white rounded-lg p-2">
            <p class="text-base font-bold ${p.price_cagr > 0 ? 'text-green-700' : 'text-red-700'}">
              ${p.price_cagr > 0 ? '+' : ''}${p.price_cagr.toFixed(1)}%
            </p>
            <p class="text-xs text-slate-500">2-yr CAGR</p>
          </div>
        </div>
        <div class="mt-2">
          <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${valColor}">
            ${p.valuation}
          </span>
        </div>
      </div>

      <div>
        <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Key Features
        </p>
        ${featureRow('Accessibility',     p.accessibility)}
        ${featureRow('DMRC Proximity',    p.dmrc_prox)}
        ${featureRow('Airport Proximity', p.airport_prox)}
        ${featureRow('Commercial',        p.commercial)}
        ${featureRow('Migration Rate',    p.migration_rate)}
        ${featureRow('AQI Score',         p.aqi_score)}
        ${featureRow('Crime Safety',      p.crime_score)}
      </div>

      <div>
        <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
          Simulation Impact
        </p>
        ${Object.entries(SC_CFG).map(([k, v]) => {
          const boost = p['sc_' + k] || 0;
          return `
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-xs text-slate-600 truncate mr-2" style="max-width:150px">
                ${v.label.replace('->', '\u2192').substring(0, 28)}...
              </span>
              <span class="text-xs font-bold" style="color:${v.color}">
                +${(boost * 100).toFixed(1)}%
              </span>
            </div>`;
        }).join('')}
      </div>

    </div>
  `;

  document.getElementById('side-panel').classList.add('open');
}

function scoreBar(label, val, color) {
  return `
    <div class="flex items-center gap-2 mb-1.5">
      <span class="text-xs text-slate-600 w-24 shrink-0">${label}</span>
      <div class="flex-1 bg-slate-100 rounded-full h-1.5">
        <div class="h-1.5 rounded-full transition-all"
             style="width:${val*100}%;background:${color}"></div>
      </div>
      <span class="text-xs font-semibold text-slate-700 w-8 text-right">
        ${val.toFixed(2)}
      </span>
    </div>`;
}

function featureRow(label, val) {
  const pct = Math.round(val * 100);
  const col = val > 0.6 ? '#16a34a' : val > 0.3 ? '#d97706' : '#dc2626';
  return `
    <div class="flex items-center justify-between mb-1">
      <span class="text-xs text-slate-600">${label}</span>
      <div class="flex items-center gap-1.5">
        <div class="w-16 bg-slate-100 rounded-full h-1">
          <div class="h-1 rounded-full" style="width:${pct}%;background:${col}"></div>
        </div>
        <span class="text-xs text-slate-500 w-6 text-right">${pct}%</span>
      </div>
    </div>`;
}

function closePanel() {
  document.getElementById('side-panel').classList.remove('open');
}