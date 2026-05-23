// tabs.js — tab switching, legend rendering

let currentTab = 'overview';

function switchTab(tab) {
  currentTab        = tab;
  window.currentTab = tab;

  ['overview', 'potential', 'livability', 'simulations'].forEach(t => {
    document.getElementById('tab-' + t).classList.toggle('active', t === tab);
    document.getElementById('tab-' + t).classList.toggle('text-slate-600', t !== tab);
    document.getElementById('panel-' + t).classList.toggle('hidden', t !== tab);
  });

  closePanel();

  // overview ALWAYS shows trajectory regardless
  const modeMap = {
    overview:    'trajectory',
    potential:   'potential',
    livability:  'livability',
    simulations: 'scenario',
  };
  renderGeojson(modeMap[tab]);
  renderLegend(modeMap[tab]);

  const hint = document.getElementById('zoom-hint');
  hint.classList.toggle('hidden', tab !== 'potential');
  if (tab === 'potential') handleZoom();
}

function renderLegend(mode) {
  const title = document.getElementById('legend-title');
  const items = document.getElementById('legend-items');

  if (mode === 'trajectory') {
    title.textContent = 'Trajectory';
    items.innerHTML = Object.entries(TRAJ_COLORS).map(([k, c]) => `
      <div class="flex items-center gap-2">
        <div class="w-3 h-3 rounded-sm" style="background:${c}"></div>
        <span class="text-slate-600">${k}</span>
      </div>`).join('');

  } else if (mode === 'scenario') {
    title.textContent = 'Impact Boost';
    // show selected scenario colors
    if (selectedScenarios.size === 0) {
      items.innerHTML = `<p class="text-slate-400 text-xs">Select a simulation</p>`;
    } else {
      items.innerHTML = Array.from(selectedScenarios).map(key => {
        const cfg = SC_CFG[key];
        return `<div class="flex items-center gap-2">
          <div class="w-3 h-3 rounded-sm" style="background:${cfg.color}"></div>
          <span class="text-slate-600 text-xs truncate" style="max-width:100px">
            ${cfg.label.replace('->','\u2192').substring(0,20)}...
          </span>
        </div>`;
      }).join('');
    }

  } else {
    const cfg = {
      potential:  ['Low Growth',     'High Growth',     '#bfdbfe', '#1d4ed8'],
      livability: ['Low Livability', 'High Livability', '#bbf7d0', '#15803d'],
      combined:   ['Low Score',      'High Score',      '#ddd6fe', '#4c1d95'],
    }[mode];
    if (!cfg) return;
    title.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
    items.innerHTML = `
      <div class="w-24 h-3 rounded-sm"
           style="background: linear-gradient(to right, ${cfg[2]}, ${cfg[3]})">
      </div>
      <div class="flex justify-between text-slate-500 text-xs mt-0.5">
        <span>${cfg[0]}</span><span>${cfg[1]}</span>
      </div>`;
  }
}