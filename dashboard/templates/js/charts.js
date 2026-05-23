// charts.js — Chart.js chart rendering (donut, SHAP, livability, scenario)

let trajDonut, shapChart, livChart, scChart;

function renderDonut() {
  const ctx = document.getElementById('traj-donut').getContext('2d');
  trajDonut = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Accelerating', 'Emerging', 'Stable', 'Declining'],
      datasets: [{
        data: [STATS.accelerating, STATS.emerging, STATS.stable, STATS.declining],
        backgroundColor: ['#16a34a', '#2563eb', '#94a3b8', '#dc2626'],
        borderWidth: 2,
        borderColor: '#fff',
      }],
    },
    options: {
      cutout: '65%',
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 10 }, boxWidth: 12 } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.raw.toLocaleString()}` } },
      },
    },
  });
}

function renderShapChart() {
  const ctx    = document.getElementById('shap-chart').getContext('2d');
  const labels = SHAP.labels.map(l => l.replace('lag_', '[lag] '));
  shapChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data:            SHAP.values,
        backgroundColor: SHAP.labels.map(l => l.startsWith('lag_') ? '#bfdbfe' : '#3b82f6'),
        borderRadius:    4,
      }],
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid:  { color: '#f1f5f9' },
          ticks: { font: { size: 9 } },
          title: { display: true, text: 'Mean |SHAP|', font: { size: 9 } },
        },
        y: { ticks: { font: { size: 9 } } },
      },
    },
  });
}

function renderLivChart() {
  const weights = {
    'AQI': 0.25, 'Healthcare': 0.25, 'Education': 0.15,
    'Parks': 0.10, 'Recreation': 0.10, 'Civic': 0.10, 'Crime Safety': 0.05,
  };
  const ctx = document.getElementById('liv-chart').getContext('2d');
  livChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: Object.keys(weights),
      datasets: [{
        data:            Object.values(weights).map(v => v * 100),
        backgroundColor: ['#6366f1','#10b981','#f59e0b','#22c55e','#8b5cf6','#06b6d4','#f43f5e'],
        borderRadius:    4,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        y: {
          ticks:    { callback: v => v + '%', font: { size: 9 } },
          grid:     { color: '#f1f5f9' },
        },
        x: { ticks: { font: { size: 9 } } },
      },
    },
  });
}

function renderScChart() {
  const ctx = document.getElementById('sc-chart').getContext('2d');
  scChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels:   SCENARIOS.map(s => s.label.replace('->', '->').substring(0, 20) + '...'),
      datasets: [{
        label:           'Cells Reclassified',
        data:            SCENARIOS.map(s => s.reclassified),
        backgroundColor: SCENARIOS.map(s => s.color),
        borderRadius:    4,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        y: {
          grid:  { color: '#f1f5f9' },
          ticks: { font: { size: 9 }, callback: v => v.toLocaleString() },
        },
        x: { ticks: { font: { size: 8 }, maxRotation: 15 } },
      },
    },
  });
}