"""Write all improved templates to disk."""
import os

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# ─── map.html ─────────────────────────────────────────────────────────────────
MAP_HTML = r"""{% extends "base.html" %}
{% block title %}Interactive Risk Map{% endblock %}
{% block page_title %}<i class="fas fa-globe me-2 text-primary"></i>Interactive Risk Map{% endblock %}
{% block breadcrumb %}60 neighbourhoods colour-coded by heat-risk level — click any marker for details{% endblock %}

{% block head %}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
#map{height:calc(100vh - 190px);border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.12)}
.map-filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.filter-btn{padding:6px 16px;border-radius:20px;border:2px solid transparent;
  font-size:12.5px;font-weight:600;cursor:pointer;transition:all .18s}
.filter-btn.f-all      {background:#1e293b;color:#fff;border-color:#1e293b}
.filter-btn.f-high     {background:#fee2e2;color:#991b1b;border-color:#fca5a5}
.filter-btn.f-medium   {background:#fef9c3;color:#854d0e;border-color:#fde047}
.filter-btn.f-low      {background:#dcfce7;color:#166534;border-color:#86efac}
.filter-btn.f-review   {background:#eff6ff;color:#1e40af;border-color:#93c5fd}
.filter-btn.f-escalated{background:#fdf4ff;color:#6b21a8;border-color:#d8b4fe}
.filter-btn.active     {filter:brightness(0.84);box-shadow:0 0 0 3px rgba(0,0,0,.18)}
.map-legend .ld{display:inline-block;width:13px;height:13px;border-radius:50%;margin-right:6px;vertical-align:middle}
</style>
{% endblock %}

{% block content %}
<div class="map-filters">
  <button class="filter-btn f-all active" onclick="filterMap('all',this)"><i class="fas fa-globe me-1"></i>All</button>
  <button class="filter-btn f-high"       onclick="filterMap('high',this)"><i class="fas fa-fire me-1"></i>High Risk</button>
  <button class="filter-btn f-medium"     onclick="filterMap('medium',this)"><i class="fas fa-exclamation me-1"></i>Medium</button>
  <button class="filter-btn f-low"        onclick="filterMap('low',this)"><i class="fas fa-check me-1"></i>Low Risk</button>
  <button class="filter-btn f-review"     onclick="filterMap('review',this)"><i class="fas fa-clipboard-check me-1"></i>Needs Review</button>
  <button class="filter-btn f-escalated"  onclick="filterMap('escalated',this)"><i class="fas fa-exclamation-triangle me-1"></i>Escalated</button>
</div>
<div class="row g-3">
  <div class="col-lg-9"><div id="map"></div></div>
  <div class="col-lg-3">
    <div class="card h-100">
      <div class="card-header"><i class="fas fa-layer-group me-2 text-primary"></i>Legend & Stats</div>
      <div class="card-body">
        <div class="map-legend" style="font-size:13px;line-height:2">
          <div><span class="ld" style="background:#ef4444"></span>High Risk</div>
          <div><span class="ld" style="background:#f97316"></span>Medium Risk</div>
          <div><span class="ld" style="background:#22c55e"></span>Low Risk</div>
          <div><span class="ld" style="background:#a855f7"></span>Ambiguous</div>
          <div><span class="ld" style="background:#1a56db;outline:2px solid #7c3aed;outline-offset:2px"></span>Escalated</div>
        </div>
        <hr>
        <div class="fw-700 small mb-1">Visible</div>
        <div id="visCount" class="badge bg-secondary" style="font-size:13px">All 60</div>
        <hr>
        <div class="fw-700 small mb-1 mt-1">Instructions</div>
        <div style="font-size:12px;color:#64748b">Click any marker to see full details and navigate to the neighbourhood page.</div>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const MAP_DATA = {{ map_data | safe }};
const COLOURS  = {High:'#ef4444',Medium:'#f97316',Low:'#22c55e',
                  AMBIGUOUS:'#a855f7',MISSING_DATA:'#94a3b8',EXTREME_VALUE:'#f59e0b'};

const leafMap = L.map('map').setView([-33.87, 151.21], 11);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
  {attribution:'&copy; OpenStreetMap contributors', maxZoom:18}).addTo(leafMap);

const allMarkers = [];

MAP_DATA.forEach(nb => {
  if (!nb.latitude || !nb.longitude) return;
  const col = COLOURS[nb.risk_level] || '#94a3b8';
  const m = L.circleMarker([nb.latitude, nb.longitude], {
    radius:9, fillColor:col,
    color: nb.has_escalation ? '#7c3aed' : '#fff',
    weight: nb.has_escalation ? 3 : 1.5,
    opacity:1, fillOpacity:0.88
  });
  const revBadge = nb.needs_review   ? `<span class="badge bg-warning text-dark ms-1" style="font-size:10px">Review</span>` : '';
  const escBadge = nb.has_escalation ? `<span class="badge bg-danger ms-1" style="font-size:10px">Escalated</span>` : '';
  m.bindPopup(`
    <div style="font-family:'Inter',sans-serif;min-width:200px">
      <div style="font-weight:800;font-size:14px;margin-bottom:6px">${nb.neighbourhood_name}</div>
      <div style="margin-bottom:8px">
        <span class="badge" style="background:${col}">${nb.risk_level}</span>
        ${revBadge}${escBadge}
      </div>
      <table style="font-size:12px;width:100%;border-collapse:collapse">
        <tr><td style="color:#64748b;padding:2px 4px">Risk Score</td><td style="font-weight:700">${nb.risk_score ?? 'N/A'}</td></tr>
        <tr><td style="color:#64748b;padding:2px 4px">Temperature</td><td>${nb.temperature ? nb.temperature+'°C' : 'N/A'}</td></tr>
        <tr><td style="color:#64748b;padding:2px 4px">Vulnerability</td><td>${nb.vulnerability_score ?? 'N/A'}</td></tr>
        <tr><td style="color:#64748b;padding:2px 4px">Service Access</td><td>${nb.service_access_score ?? 'N/A'}</td></tr>
        <tr><td style="color:#64748b;padding:2px 4px">Comm. Reach</td><td>${nb.communication_reach_percentage ? nb.communication_reach_percentage+'%' : 'N/A'}</td></tr>
      </table>
      <a href="/neighbourhood/${nb.neighbourhood_id}"
         style="display:block;margin-top:10px;text-align:center;padding:7px;
                background:#1a56db;color:#fff;border-radius:7px;font-size:12px;
                text-decoration:none;font-weight:700">
        View Full Details &rarr;
      </a>
    </div>
  `);
  m._nb = nb;
  m.addTo(leafMap);
  allMarkers.push(m);
});

function filterMap(type, btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  let visible = 0;
  allMarkers.forEach(m => {
    const nb = m._nb;
    let show = type === 'all'
      || (type === 'high'      && nb.risk_level === 'High')
      || (type === 'medium'    && nb.risk_level === 'Medium')
      || (type === 'low'       && nb.risk_level === 'Low')
      || (type === 'review'    && nb.needs_review)
      || (type === 'escalated' && nb.has_escalation);
    show ? (m.addTo(leafMap), visible++) : m.remove();
  });
  document.getElementById('visCount').textContent = `${visible} shown`;
}
</script>
{% endblock %}
"""

# ─── data_quality.html ────────────────────────────────────────────────────────
DATA_QUALITY_HTML = r"""{% extends "base.html" %}
{% block title %}Data Quality{% endblock %}
{% block page_title %}<i class="fas fa-clipboard-list me-2 text-primary"></i>Data Quality Report{% endblock %}
{% block breadcrumb %}Pre-computation data validation — checked before every risk classification{% endblock %}

{% block content %}
<!-- Summary KPIs -->
<div class="row g-3 mb-4">
  <div class="col-6 col-md-3 col-lg-2">
    <div class="stat-card"><div class="stat-number">{{ summary.total }}</div><div class="stat-label">Total Records</div></div>
  </div>
  <div class="col-6 col-md-3 col-lg-2">
    <div class="stat-card" style="border-left:4px solid #22c55e">
      <div class="stat-number" style="color:#22c55e">{{ summary.ok }}</div><div class="stat-label">Fully Valid</div>
    </div>
  </div>
  <div class="col-6 col-md-3 col-lg-2">
    <div class="stat-card" style="border-left:4px solid #f97316">
      <div class="stat-number" style="color:#f97316">{{ summary.warning }}</div><div class="stat-label">Warnings</div>
    </div>
  </div>
  <div class="col-6 col-md-3 col-lg-2">
    <div class="stat-card" style="border-left:4px solid #ef4444">
      <div class="stat-number" style="color:#ef4444">{{ summary.critical }}</div><div class="stat-label">Critical Issues</div>
    </div>
  </div>
  <div class="col-6 col-md-3 col-lg-2">
    <div class="stat-card" style="border-left:4px solid #f59e0b">
      <div class="stat-number" style="color:#f59e0b">{{ summary.missing_any }}</div><div class="stat-label">Missing Fields</div>
    </div>
  </div>
  <div class="col-6 col-md-3 col-lg-2">
    <div class="stat-card" style="border-left:4px solid #1a56db">
      <div class="stat-number" style="color:#1a56db">{{ summary.avg_quality }}</div><div class="stat-label">Avg Quality Score</div>
    </div>
  </div>
</div>

<!-- Quality donut context -->
<div class="row g-3 mb-4">
  <div class="col-md-4">
    <div class="card h-100">
      <div class="card-header"><i class="fas fa-chart-pie me-2 text-primary"></i>Quality Distribution</div>
      <div class="card-body" style="max-height:220px">
        <canvas id="qualityDonut"></canvas>
      </div>
    </div>
  </div>
  <div class="col-md-8">
    <div class="card h-100">
      <div class="card-header"><i class="fas fa-info-circle me-2 text-primary"></i>What is Checked</div>
      <div class="card-body">
        <div class="row g-2">
          {% for check in [
            ('Missing Values','Temperature, vulnerability score, service access, built environment score must not be NULL or NaN.','fas fa-exclamation-circle','text-warning'),
            ('Duplicate Records','neighbourhood_id must be unique across all records.','fas fa-copy','text-primary'),
            ('Invalid Values','Vulnerability score must be in [0,100]. Temperature must be > 0.','fas fa-times-circle','text-danger'),
            ('Extreme Outliers','Temperature > 52°C is outside plausible range — likely sensor error.','fas fa-bolt','text-warning'),
            ('Quality Score','100 points minus penalties: 20 per missing, 15 per invalid, 10 per outlier.','fas fa-star','text-success'),
          ] %}
          <div class="col-md-6">
            <div style="background:#f8fafc;border-radius:8px;padding:10px 12px;font-size:12.5px">
              <div class="fw-700 mb-1"><i class="{{ check[2] }} {{ check[3] }} me-1"></i>{{ check[0] }}</div>
              <div style="color:#64748b">{{ check[1] }}</div>
            </div>
          </div>
          {% endfor %}
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Data Table -->
<div class="card">
  <div class="card-header d-flex justify-content-between align-items-center">
    <span><i class="fas fa-table me-2 text-primary"></i>Record-Level Quality Report</span>
    <div class="d-flex gap-2 align-items-center">
      <input type="text" id="dqSearch" class="form-control form-control-sm" placeholder="Search..." style="width:200px">
      <a href="{{ url_for('api_data_quality') }}" class="btn btn-sm btn-outline-secondary" target="_blank">
        <i class="fas fa-code me-1"></i>JSON API
      </a>
    </div>
  </div>
  <div class="card-body p-0">
    <div style="overflow-x:auto">
      <table class="table table-hover mb-0" id="dqTable">
        <thead style="background:#f8fafc">
          <tr>
            <th>ID</th><th>Neighbourhood</th><th>Risk Level</th>
            <th>Quality Score</th><th>Status</th>
            <th>Missing</th><th>Invalid</th><th>Outliers</th><th>Issues</th>
          </tr>
        </thead>
        <tbody>
          {% for r in report %}
          <tr>
            <td><small class="text-muted">{{ r.neighbourhood_id }}</small></td>
            <td>
              <a href="{{ url_for('neighbourhood_detail', nb_id=r.neighbourhood_id) }}"
                 style="text-decoration:none;font-weight:600">
                {{ r.neighbourhood_name }}
              </a>
            </td>
            <td>
              <span class="badge-risk badge-{{ r.risk_level }}">{{ r.risk_level }}</span>
            </td>
            <td>
              <div style="display:flex;align-items:center;gap:8px">
                <div style="background:#e2e8f0;border-radius:4px;height:8px;width:80px;overflow:hidden">
                  <div style="width:{{ r.quality_score }}%;height:8px;background:{{ '#22c55e' if r.quality_score>=80 else ('#f97316' if r.quality_score>=60 else '#ef4444') }};border-radius:4px"></div>
                </div>
                <span style="font-weight:700;font-size:13px;color:{{ '#22c55e' if r.quality_score>=80 else ('#f97316' if r.quality_score>=60 else '#ef4444') }}">
                  {{ r.quality_score }}
                </span>
              </div>
            </td>
            <td>
              {% if r.status == 'OK' %}
                <span class="badge bg-success">OK</span>
              {% elif r.status == 'WARNING' %}
                <span class="badge bg-warning text-dark">Warning</span>
              {% else %}
                <span class="badge bg-danger">Critical</span>
              {% endif %}
            </td>
            <td>
              {% if r.missing_count > 0 %}
                <span class="badge bg-warning text-dark">{{ r.missing_count }}</span>
              {% else %}
                <span class="text-muted">0</span>
              {% endif %}
            </td>
            <td>
              {% if r.invalid_count > 0 %}
                <span class="badge bg-danger">{{ r.invalid_count }}</span>
              {% else %}
                <span class="text-muted">0</span>
              {% endif %}
            </td>
            <td>
              {% if r.outlier_count > 0 %}
                <span class="badge bg-warning text-dark">{{ r.outlier_count }}</span>
              {% else %}
                <span class="text-muted">0</span>
              {% endif %}
            </td>
            <td>
              {% if r.issues %}
                <details>
                  <summary style="cursor:pointer;font-size:12px;color:#1a56db">
                    {{ r.issues|length }} issue(s)
                  </summary>
                  <ul style="font-size:11.5px;margin:4px 0 0 0;padding-left:16px;color:#64748b">
                    {% for issue in r.issues %}
                      <li>{{ issue }}</li>
                    {% endfor %}
                  </ul>
                </details>
              {% else %}
                <span class="text-muted small">None</span>
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
// Search filter
document.getElementById('dqSearch').addEventListener('input', function() {
  const q = this.value.toLowerCase();
  document.querySelectorAll('#dqTable tbody tr').forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
});

// Quality donut chart
const ctx = document.getElementById('qualityDonut').getContext('2d');
new Chart(ctx, {
  type: 'doughnut',
  data: {
    labels: ['Valid', 'Warning', 'Critical'],
    datasets: [{
      data: [{{ summary.ok }}, {{ summary.warning }}, {{ summary.critical }}],
      backgroundColor: ['#22c55e','#f97316','#ef4444'],
      borderWidth: 2, borderColor: '#fff'
    }]
  },
  options: {
    responsive: true, maintainAspectRatio: true,
    plugins: { legend: { position: 'bottom', labels: { font: { family: 'Inter', size: 12 } } } }
  }
});
</script>
{% endblock %}
"""

# ─── Write files ──────────────────────────────────────────────────────────────
files = {
    "templates/map.html":          MAP_HTML,
    "templates/data_quality.html": DATA_QUALITY_HTML,
}

for path, content in files.items():
    full = os.path.join(os.path.dirname(__file__), path)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Written: {path}  ({len(content.splitlines())} lines)")
