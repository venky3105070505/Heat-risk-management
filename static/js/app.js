/* app.js – shared chart helpers and UI interactions */

// ── Colour map for risk levels ────────────────────────────────────────────────
const RISK_COLORS = {
  High:           '#ef4444',
  Medium:         '#f97316',
  Low:            '#22c55e',
  AMBIGUOUS:      '#a855f7',
  MISSING_DATA:   '#a855f7',
  EXTREME_VALUE:  '#a855f7',
};

const RISK_BG = {
  High:    'rgba(239,68,68,.12)',
  Medium:  'rgba(249,115,22,.12)',
  Low:     'rgba(34,197,94,.12)',
  AMBIGUOUS: 'rgba(168,85,247,.12)',
};

// ── Risk distribution donut ───────────────────────────────────────────────────
function initRiskDonut(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.labels,
      datasets: [{
        data: data.values,
        backgroundColor: data.labels.map(l => RISK_COLORS[l] || '#94a3b8'),
        borderWidth: 2,
        borderColor: '#ffffff',
        hoverOffset: 6,
      }],
    },
    options: {
      cutout: '68%',
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, font: { size: 12, weight: '600' } } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed}` } },
      },
    },
  });
}

// ── Scatter plot helper ───────────────────────────────────────────────────────
function initScatter(canvasId, data, xLabel, yLabel) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;

  // Group by risk level
  const groups = {};
  data.forEach(d => {
    if (!groups[d.level]) groups[d.level] = [];
    groups[d.level].push({ x: d.x, y: d.y, name: d.name });
  });

  const datasets = Object.entries(groups).map(([level, pts]) => ({
    label: level,
    data: pts,
    backgroundColor: RISK_BG[level]   || 'rgba(148,163,184,.2)',
    borderColor:     RISK_COLORS[level] || '#94a3b8',
    pointRadius: 5,
    pointHoverRadius: 7,
  }));

  new Chart(ctx, {
    type: 'scatter',
    data: { datasets },
    options: {
      scales: {
        x: { title: { display: true, text: xLabel, font: { weight: '600', size: 12 } } },
        y: { title: { display: true, text: yLabel, font: { weight: '600', size: 12 } },
             min: 0, max: 100 },
      },
      plugins: {
        legend: { position: 'top', labels: { font: { size: 12, weight: '600' } } },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.raw.name}: (${ctx.raw.x}, ${ctx.raw.y})`,
          },
        },
      },
    },
  });
}

// ── Horizontal bar ranking chart ──────────────────────────────────────────────
function initRankingBar(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const colors = data.levels.map(l => RISK_COLORS[l] || '#94a3b8');
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [{
        label: 'Risk Score',
        data: data.values,
        backgroundColor: colors,
        borderRadius: 4,
        borderSkipped: false,
      }],
    },
    options: {
      indexAxis: 'y',
      scales: {
        x: { min: 0, max: 100, title: { display: true, text: 'Risk Score' } },
        y: { ticks: { font: { size: 11 } } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// ── Contribution breakdown bar ────────────────────────────────────────────────
function initContribBar(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !data) return;
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [{
        label: 'Contribution to Risk Score (%)',
        data: data.values,
        backgroundColor: ['#ef4444', '#f97316', '#3b82f6', '#22c55e'],
        borderRadius: 6,
      }],
    },
    options: {
      scales: {
        y: { beginAtZero: true, max: 40, title: { display: true, text: 'Score Points' } },
      },
      plugins: { legend: { display: false } },
    },
  });
}

// ── Strategy comparison grouped bar ──────────────────────────────────────────
function initStrategyChart(canvasId, comparison) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const metrics = [
    'neighbourhoods_reached',
    'high_risk_covered_pct',
    'resource_usage_pct',
    'urgent_areas_missed',
    'avg_risk_score',
  ];
  const labels = [
    'Areas Reached', 'High-Risk Covered %',
    'Resource Usage %', 'Urgent Areas Missed', 'Avg Risk Score',
  ];
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Objective A: Max Coverage',
          data: metrics.map(m => comparison.obj_a[m]),
          backgroundColor: 'rgba(59,130,246,.7)',
          borderRadius: 4,
        },
        {
          label: 'Objective B: Resource Efficiency',
          data: metrics.map(m => comparison.obj_b[m]),
          backgroundColor: 'rgba(34,197,94,.7)',
          borderRadius: 4,
        },
      ],
    },
    options: {
      scales: { y: { beginAtZero: true } },
      plugins: { legend: { position: 'top' } },
    },
  });
}

// ── Experiment bar chart ──────────────────────────────────────────────────────
function initExperimentChart(canvasId, metrics) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const labels = ['High-Risk Reached %', 'Precision %', 'Recall %', 'Resource Util %'];
  const baseline = [
    metrics.baseline.high_reached_pct,
    metrics.baseline.precision,
    metrics.baseline.recall,
    metrics.baseline.resource_util_pct,
  ];
  const proposed = [
    metrics.proposed.high_reached_pct,
    metrics.proposed.precision,
    metrics.proposed.recall,
    metrics.proposed.resource_util_pct,
  ];
  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Baseline (Generic Advisory)', data: baseline,
          backgroundColor: 'rgba(148,163,184,.7)', borderRadius: 4 },
        { label: 'Proposed (Targeted)', data: proposed,
          backgroundColor: 'rgba(26,86,219,.7)',  borderRadius: 4 },
      ],
    },
    options: {
      scales: { y: { beginAtZero: true, max: 110 } },
      plugins: { legend: { position: 'top' } },
    },
  });
}

// ── Feedback radar chart ──────────────────────────────────────────────────────
function initFeedbackRadar(canvasId, averages) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: 'radar',
    data: {
      labels: ['Risk Understandable', 'Escalation Clear', 'Actions Useful', 'Dashboard Easy'],
      datasets: [{
        label: 'Average Score (out of 5)',
        data: [averages.q1, averages.q2, averages.q3, averages.q4],
        backgroundColor: 'rgba(26,86,219,.15)',
        borderColor: '#1a56db',
        pointBackgroundColor: '#1a56db',
        pointRadius: 5,
      }],
    },
    options: {
      scales: { r: { min: 0, max: 5, ticks: { stepSize: 1 } } },
      plugins: { legend: { display: false } },
    },
  });
}

// ── Leaflet map initialisation (called from map.html) ────────────────────────
function initMap(mapData) {
  const map = L.map('map').setView([-33.87, 151.21], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
  }).addTo(map);

  const colorFor = level => ({
    High: '#ef4444', Medium: '#f97316', Low: '#22c55e',
    AMBIGUOUS: '#a855f7', MISSING_DATA: '#a855f7', EXTREME_VALUE: '#a855f7',
  }[level] || '#94a3b8');

  mapData.forEach(nb => {
    if (!nb.latitude || !nb.longitude) return;
    const color = colorFor(nb.risk_level);
    const marker = L.circleMarker([nb.latitude, nb.longitude], {
      radius: 9,
      fillColor: color,
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85,
    }).addTo(map);

    const score = nb.risk_score != null ? nb.risk_score.toFixed(1) : 'N/A';
    marker.bindPopup(`
      <div style="min-width:200px;font-family:Inter,sans-serif">
        <div style="font-weight:700;font-size:14px;margin-bottom:8px">${nb.neighbourhood_name}</div>
        <table style="width:100%;font-size:12px;border-collapse:collapse">
          <tr><td style="color:#64748b;padding:2px 0">Risk Level</td>
              <td style="font-weight:600;color:${color}">${nb.risk_level}</td></tr>
          <tr><td style="color:#64748b;padding:2px 0">Risk Score</td>
              <td style="font-weight:600">${score}</td></tr>
          <tr><td style="color:#64748b;padding:2px 0">Temperature</td>
              <td>${nb.temperature != null ? nb.temperature + '°C' : 'Missing'}</td></tr>
          <tr><td style="color:#64748b;padding:2px 0">Vulnerability</td>
              <td>${nb.vulnerability_score != null ? nb.vulnerability_score : 'N/A'}</td></tr>
          <tr><td style="color:#64748b;padding:2px 0">Service Access</td>
              <td>${nb.service_access_score != null ? nb.service_access_score : 'N/A'}</td></tr>
          <tr><td style="color:#64748b;padding:2px 0">Built Env.</td>
              <td>${nb.built_environment_score != null ? nb.built_environment_score : 'N/A'}</td></tr>
        </table>
        <a href="/neighbourhood/${nb.neighbourhood_id}"
           style="display:block;margin-top:10px;text-align:center;background:#1a56db;
                  color:#fff;padding:6px;border-radius:6px;font-size:12px;font-weight:600;
                  text-decoration:none">View Details →</a>
      </div>
    `);
  });
}

// ── Slider live value display ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.soft-slider').forEach(slider => {
    const valEl = document.getElementById(slider.id + '_val');
    if (valEl) {
      valEl.textContent = parseFloat(slider.value).toFixed(1);
      slider.addEventListener('input', () => {
        valEl.textContent = parseFloat(slider.value).toFixed(1);
      });
    }
  });

  // Initialize theme on load
  initTheme();

  // Initialize global search
  initGlobalSearch();
});

// ── Dark / Light Mode Toggle ─────────────────────────────────────────────────
function initTheme() {
  const savedTheme = localStorage.getItem('heat_planner_theme') || 'light';
  applyTheme(savedTheme);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('heat_planner_theme', theme);
  const icon = document.getElementById('themeIcon');
  if (icon) {
    if (theme === 'dark') {
      icon.classList.remove('fa-moon');
      icon.classList.add('fa-sun');
      icon.style.color = '#f59e0b';
    } else {
      icon.classList.remove('fa-sun');
      icon.classList.add('fa-moon');
      icon.style.color = '';
    }
  }
}

function toggleDarkMode() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
}

// ── Mobile Sidebar Drawer ────────────────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (!sidebar) return;
  sidebar.classList.toggle('open');
  if (backdrop) {
    backdrop.classList.toggle('show');
  }
}

// ── Global Search Dropdown ───────────────────────────────────────────────────
function initGlobalSearch() {
  const searchInput = document.getElementById('globalSearchInput');
  const resultsContainer = document.getElementById('globalSearchResults');
  if (!searchInput || !resultsContainer) return;

  let debounceTimer = null;

  searchInput.addEventListener('input', (e) => {
    clearTimeout(debounceTimer);
    const query = e.target.value.trim();
    if (query.length === 0) {
      resultsContainer.classList.remove('show');
      resultsContainer.innerHTML = '';
      return;
    }

    debounceTimer = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(results => {
          if (!results || results.length === 0) {
            resultsContainer.innerHTML = `
              <div class="p-3 text-center text-muted small">
                <i class="fas fa-search me-1"></i>No matching sectors found
              </div>`;
            resultsContainer.classList.add('show');
            return;
          }

          const badgeClass = level => {
            if (level === 'High') return 'bg-danger text-white';
            if (level === 'Medium') return 'bg-warning text-dark';
            if (level === 'Low') return 'bg-success text-white';
            return 'bg-purple text-white';
          };

          resultsContainer.innerHTML = results.slice(0, 8).map(nb => `
            <a href="/neighbourhood/${nb.id}" class="search-result-item">
              <div>
                <strong class="d-block font-size-13">${nb.name}</strong>
                <span class="text-muted" style="font-size:11px">Sector ID: ${nb.id}</span>
              </div>
              <div class="text-end">
                <span class="badge ${badgeClass(nb.risk_level)}" style="font-size:10px">${nb.risk_level}</span>
                <small class="d-block text-muted" style="font-size:10px">Score: ${nb.risk_score != null ? nb.risk_score.toFixed(1) : 'N/A'}</small>
              </div>
            </a>
          `).join('');
          resultsContainer.classList.add('show');
        })
        .catch(err => {
          console.error('Search query error:', err);
        });
    }, 200);
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !resultsContainer.contains(e.target)) {
      resultsContainer.classList.remove('show');
    }
  });

  // Close on Escape key
  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      resultsContainer.classList.remove('show');
    }
  });
}

