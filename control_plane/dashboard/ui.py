DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>RCSCE Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:       #f4f6f9;
  --surface:  #ffffff;
  --border:   #e2e7ef;
  --border2:  #cdd5e0;
  --accent:   #2563eb;
  --accent-bg:#eff6ff;
  --green:    #16a34a;
  --green-bg: #f0fdf4;
  --amber:    #d97706;
  --amber-bg: #fffbeb;
  --red:      #dc2626;
  --red-bg:   #fef2f2;
  --purple:   #7c3aed;
  --purple-bg:#f5f3ff;
  --cyan:     #0891b2;
  --cyan-bg:  #ecfeff;
  --text:     #111827;
  --text2:    #374151;
  --muted:    #6b7280;
  --muted2:   #9ca3af;
  --sans:     'DM Sans', sans-serif;
  --mono:     'DM Mono', monospace;
}

body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
}

/* ── TOP HEADER ── */
.header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.header-left { display: flex; align-items: center; gap: 16px; }

.logo-block { display: flex; align-items: center; gap: 10px; }
.logo-icon {
  width: 36px; height: 36px;
  background: var(--accent);
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
}
.logo-text { font-size: 1.1rem; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
.logo-sub { font-size: 0.75rem; color: var(--muted); font-weight: 400; }

.badge {
  font-size: 0.7rem; font-weight: 600; padding: 3px 10px;
  border-radius: 100px; letter-spacing: 0.04em;
}
.badge-blue   { background: var(--accent-bg);  color: var(--accent); }
.badge-green  { background: var(--green-bg);   color: var(--green);  }
.badge-purple { background: var(--purple-bg);  color: var(--purple); }

.header-right { display: flex; align-items: center; gap: 20px; }
.conn-indicator { display: flex; align-items: center; gap: 8px; }
.conn-dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: #d1d5db;
}
.conn-dot.connected { background: var(--green); box-shadow: 0 0 0 3px rgba(22,163,74,0.15); }
.conn-label { font-size: 0.8rem; font-weight: 500; color: var(--muted); }
.clock { font-family: var(--mono); font-size: 0.85rem; color: var(--muted); }

/* ── STAT CARDS ROW ── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  padding: 24px 32px 0;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px 22px;
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.stat-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.stat-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  border-radius: 14px 14px 0 0;
}
.stat-card.blue::before   { background: var(--accent); }
.stat-card.green::before  { background: var(--green);  }
.stat-card.amber::before  { background: var(--amber);  }
.stat-card.cyan::before   { background: var(--cyan);   }
.stat-card.red::before    { background: var(--red);    }
.stat-card.purple::before { background: var(--purple); }

.stat-label { font-size: 0.72rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 10px; }
.stat-value { font-family: var(--mono); font-size: 2rem; font-weight: 500; line-height: 1; color: var(--text); }
.stat-sub { font-size: 0.72rem; color: var(--muted2); margin-top: 6px; }

/* ── PIPELINE STRIP ── */
.pipeline-strip {
  margin: 20px 32px 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 18px 28px;
  display: flex;
  align-items: center;
  overflow-x: auto;
  gap: 0;
}
.pipe-step { display: flex; flex-direction: column; align-items: center; gap: 5px; min-width: 96px; }
.pipe-icon {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem;
  position: relative;
  transition: transform 0.2s;
}
.pipe-icon.active::after {
  content: '';
  position: absolute; inset: -4px;
  border-radius: 15px;
  border: 2px solid currentColor;
  opacity: 0.35;
  animation: ripple 1.5s infinite;
}
@keyframes ripple { 0%,100% { transform:scale(1); opacity:0.35; } 50% { transform:scale(1.08); opacity:0.1; } }
.pipe-icon.blue   { background: var(--accent-bg);  color: var(--accent); }
.pipe-icon.green  { background: var(--green-bg);   color: var(--green);  }
.pipe-icon.amber  { background: var(--amber-bg);   color: var(--amber);  }
.pipe-icon.purple { background: var(--purple-bg);  color: var(--purple); }
.pipe-icon.cyan   { background: var(--cyan-bg);    color: var(--cyan);   }
.pipe-label { font-size: 0.72rem; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: 0.05em; }
.pipe-sub { font-size: 0.67rem; font-family: var(--mono); color: var(--muted); }
.pipe-arrow { color: var(--border2); font-size: 1.2rem; padding: 0 8px; padding-bottom: 18px; flex-shrink: 0; }

/* ── TABS ── */
.tabs-bar {
  margin: 24px 32px 0;
  display: flex;
  gap: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 6px;
  width: fit-content;
}
.tab-btn {
  padding: 9px 22px;
  border: none; background: none;
  font-family: var(--sans); font-size: 0.85rem; font-weight: 500;
  color: var(--muted); cursor: pointer;
  border-radius: 8px;
  transition: all 0.15s;
  display: flex; align-items: center; gap: 8px;
}
.tab-btn:hover { background: var(--bg); color: var(--text); }
.tab-btn.active { background: var(--accent); color: #fff; font-weight: 600; }
.tab-btn .tab-count {
  background: rgba(255,255,255,0.25);
  border-radius: 100px;
  font-size: 0.7rem;
  padding: 1px 7px;
  font-family: var(--mono);
}
.tab-btn:not(.active) .tab-count {
  background: var(--border);
  color: var(--muted);
}

/* ── TAB PANELS ── */
.tab-content { display: none; padding: 20px 32px 40px; }
.tab-content.active { display: block; }

/* ── TABLE ── */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 20px;
}
.card-header {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
}
.card-title { font-size: 0.95rem; font-weight: 600; color: var(--text); }
.card-body { padding: 0; }
.card-body.padded { padding: 20px 24px; }

table { width: 100%; border-collapse: collapse; }
thead th {
  text-align: left;
  padding: 12px 20px;
  font-size: 0.72rem; font-weight: 600;
  color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
tbody td {
  padding: 14px 20px;
  font-size: 0.85rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: var(--bg); }

.mono { font-family: var(--mono); font-size: 0.8rem; }

/* ── STATUS PILL ── */
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 0.78rem; font-weight: 500;
  padding: 4px 12px; border-radius: 100px;
}
.pill-green  { background: var(--green-bg);   color: var(--green);  }
.pill-red    { background: var(--red-bg);      color: var(--red);    }
.pill-amber  { background: var(--amber-bg);    color: var(--amber);  }
.pill-muted  { background: var(--bg);          color: var(--muted);  border: 1px solid var(--border); }
.pill .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }

/* ── VULN BADGES ── */
.vuln-badge {
  display: inline-flex; align-items: center;
  font-size: 0.72rem; font-weight: 600; font-family: var(--mono);
  padding: 3px 10px; border-radius: 6px; margin-right: 4px;
}
.vuln-c { background: var(--red-bg);    color: var(--red);   }
.vuln-h { background: var(--amber-bg);  color: var(--amber); }
.vuln-ok{ background: var(--green-bg);  color: var(--green); }

/* ── CRITICAL TAG ── */
.crit-tag { background: var(--red-bg); color: var(--red); border: 1px solid rgba(220,38,38,0.2); font-size: 0.7rem; font-weight: 600; padding: 3px 9px; border-radius: 6px; }

/* ── EVENT FEED ── */
.event-feed { display: flex; flex-direction: column; gap: 8px; }
.event-row {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 14px 18px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  animation: slideIn 0.2s ease;
}
@keyframes slideIn { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }
.event-time { font-family: var(--mono); font-size: 0.75rem; color: var(--muted); white-space: nowrap; padding-top: 2px; min-width: 72px; }
.event-type-badge {
  font-family: var(--mono); font-size: 0.72rem; font-weight: 600;
  padding: 3px 10px; border-radius: 6px; white-space: nowrap;
}
.event-detail-text { font-size: 0.82rem; color: var(--text2); line-height: 1.4; }

/* ── WORKER CARDS ── */
.worker-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.worker-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px;
}
.worker-card.dead { border-color: rgba(220,38,38,0.3); background: var(--red-bg); }
.worker-id { font-family: var(--mono); font-size: 0.78rem; color: var(--text); margin-bottom: 14px; font-weight: 500; }
.worker-row { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; font-size: 0.82rem; }
.worker-row-label { color: var(--muted); }
.worker-row-val { font-family: var(--mono); font-weight: 500; color: var(--text2); }

/* ── CACHE PANEL ── */
.cache-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.cache-stat-row { display: flex; justify-content: space-between; align-items: center; padding: 14px 0; border-bottom: 1px solid var(--border); }
.cache-stat-row:last-child { border-bottom: none; }
.cache-stat-label { font-size: 0.85rem; color: var(--text2); }
.cache-stat-val { font-family: var(--mono); font-size: 1.1rem; font-weight: 500; }
.hit-rate-bar { margin-top: 16px; }
.hit-rate-track { background: var(--bg); border-radius: 100px; height: 10px; overflow: hidden; margin-top: 8px; border: 1px solid var(--border); }
.hit-rate-fill { height: 100%; background: linear-gradient(90deg, var(--green), var(--cyan)); border-radius: 100px; transition: width 0.6s ease; }

/* ── EMPTY STATE ── */
.empty-state { text-align: center; padding: 56px 24px; color: var(--muted); }
.empty-state-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.4; }
.empty-state-text { font-size: 0.9rem; }

/* ── FAILOVER BANNER ── */
.failover-banner {
  position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
  background: linear-gradient(90deg, #991b1b, #b91c1c);
  padding: 14px 32px;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 4px 20px rgba(220,38,38,0.3);
  animation: slideDown 0.35s ease;
}
@keyframes slideDown { from { transform:translateY(-100%); } to { transform:translateY(0); } }
.failover-banner-left { display: flex; align-items: center; gap: 14px; }
.failover-banner-icon { font-size: 1.5rem; }
.failover-banner-title { font-size: 0.9rem; font-weight: 700; color: #fecaca; }
.failover-banner-sub { font-size: 0.77rem; color: #fca5a5; margin-top: 2px; }
.failover-banner-btn {
  font-family: var(--sans); font-size: 0.82rem; font-weight: 600;
  background: rgba(255,255,255,0.15); color: white; border: 1px solid rgba(255,255,255,0.3);
  padding: 8px 18px; border-radius: 8px; cursor: pointer;
}

/* ── TWO-COL LAYOUT ── */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.three-col { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }

/* ── CLEAR BTN ── */
.btn-ghost {
  font-size: 0.78rem; font-weight: 500;
  background: none; border: 1px solid var(--border);
  color: var(--muted); padding: 5px 14px; border-radius: 7px;
  cursor: pointer;
}
.btn-ghost:hover { border-color: var(--border2); color: var(--text2); }
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-left">
    <div class="logo-block">
      <div class="logo-icon">🛡️</div>
      <div>
        <div class="logo-text">RCSCE</div>
        <div class="logo-sub">Resilient Container Security Engine</div>
      </div>
    </div>
    <span class="badge badge-blue">Phase 5</span>
    <span class="badge badge-green">Control Plane</span>
    <span class="badge badge-purple">AOS · TAMU-CC · Code Gems</span>
  </div>
  <div class="header-right">
    <span class="clock" id="clock">--:--:--</span>
    <div class="conn-indicator">
      <span class="conn-dot" id="conn-dot"></span>
      <span class="conn-label" id="conn-label">DISCONNECTED</span>
    </div>
  </div>
</div>

<!-- STAT CARDS -->
<div class="stats-row">
  <div class="stat-card blue">
    <div class="stat-label">Total Events</div>
    <div class="stat-value" id="m-events">0</div>
    <div class="stat-sub">since startup</div>
  </div>
  <div class="stat-card green">
    <div class="stat-label">Running</div>
    <div class="stat-value" id="m-running">0</div>
    <div class="stat-sub">containers</div>
  </div>
  <div class="stat-card amber">
    <div class="stat-label">Queue Depth</div>
    <div class="stat-value" id="m-queue">0</div>
    <div class="stat-sub">pending jobs</div>
  </div>
  <div class="stat-card cyan">
    <div class="stat-label">Cache Hits</div>
    <div class="stat-value" id="m-cache-hits">0</div>
    <div class="stat-sub" id="m-cache-ratio">0% hit rate</div>
  </div>
  <div class="stat-card red">
    <div class="stat-label">Auto-Failovers</div>
    <div class="stat-value" id="m-failovers">0</div>
    <div class="stat-sub">replicas created</div>
  </div>
  <div class="stat-card purple">
    <div class="stat-label">Critical</div>
    <div class="stat-value" id="m-critical">0</div>
    <div class="stat-sub">marked containers</div>
  </div>
</div>

<!-- PIPELINE -->
<div class="pipeline-strip">
  <div class="pipe-step">
    <div class="pipe-icon blue active" id="pipe-docker">🐳</div>
    <div class="pipe-label">Docker</div>
    <div class="pipe-sub" id="pipe-docker-sub">listening</div>
  </div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step">
    <div class="pipe-icon blue" id="pipe-listener">📡</div>
    <div class="pipe-label">Listener</div>
    <div class="pipe-sub" id="pipe-listener-sub">events</div>
  </div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step">
    <div class="pipe-icon cyan" id="pipe-cache">⚡</div>
    <div class="pipe-label">Cache</div>
    <div class="pipe-sub" id="pipe-cache-sub">check</div>
  </div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step">
    <div class="pipe-icon amber" id="pipe-queue">📋</div>
    <div class="pipe-label">Queue</div>
    <div class="pipe-sub" id="pipe-queue-sub">0 jobs</div>
  </div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step">
    <div class="pipe-icon purple" id="pipe-dispatch">⚙️</div>
    <div class="pipe-label">Dispatch</div>
    <div class="pipe-sub" id="pipe-dispatch-sub">0 workers</div>
  </div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step">
    <div class="pipe-icon green" id="pipe-scan">🔍</div>
    <div class="pipe-label">Scan</div>
    <div class="pipe-sub" id="pipe-scan-sub">Trivy</div>
  </div>
  <div class="pipe-arrow">→</div>
  <div class="pipe-step">
    <div class="pipe-icon green" id="pipe-failover">🛡️</div>
    <div class="pipe-label">Failover</div>
    <div class="pipe-sub" id="pipe-failover-sub">resilience</div>
  </div>
</div>

<!-- TABS -->
<div class="tabs-bar">
  <button class="tab-btn active" onclick="switchTab('containers')">🐳 Containers <span class="tab-count" id="tab-count-containers">0</span></button>
  <button class="tab-btn" onclick="switchTab('events')">📡 Live Events <span class="tab-count" id="tab-count-events">0</span></button>
  <button class="tab-btn" onclick="switchTab('workers')">⚙️ Workers <span class="tab-count" id="tab-count-workers">0</span></button>
  <button class="tab-btn" onclick="switchTab('cache')">⚡ Cache</button>
  <button class="tab-btn" onclick="switchTab('audit')">📜 Audit Log <span class="tab-count" id="tab-count-audit">0</span></button>
  <button class="tab-btn" onclick="switchTab('health')">❤️ Health</button>
</div>

<!-- TAB: CONTAINERS -->
<div class="tab-content active" id="tab-containers">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Active Containers</div>
      <span id="container-count" style="font-size:0.82rem;color:var(--muted);">0 containers</span>
    </div>
    <div class="card-body">
      <table>
        <thead>
          <tr>
            <th>Container ID</th>
            <th>Name</th>
            <th>Image</th>
            <th>Status</th>
            <th>Vulnerabilities</th>
            <th>Critical</th>
          </tr>
        </thead>
        <tbody id="container-tbody">
          <tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon">🐳</div><div class="empty-state-text">No containers yet — run a Docker container to get started</div></div></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- TAB: EVENTS -->
<div class="tab-content" id="tab-events">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Live Event Feed</div>
      <span id="event-count-tag" style="font-size:0.82rem;color:var(--muted);">0 events</span>
    </div>
    <div class="card-body padded">
      <div class="event-feed" id="event-list">
        <div class="empty-state"><div class="empty-state-icon">📡</div><div class="empty-state-text">Waiting for Docker events...</div></div>
      </div>
    </div>
  </div>
</div>

<!-- TAB: WORKERS -->
<div class="tab-content" id="tab-workers">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Worker Nodes</div>
      <span id="worker-count-tag" style="font-size:0.82rem;color:var(--muted);">0 workers</span>
    </div>
    <div class="card-body padded">
      <div class="worker-grid" id="worker-grid">
        <div class="empty-state"><div class="empty-state-icon">⚙️</div><div class="empty-state-text">No workers registered yet</div></div>
      </div>
    </div>
  </div>

  <!-- Scan Queue below workers -->
  <div class="card">
    <div class="card-header">
      <div class="card-title">Scan Queue</div>
      <span id="queue-tag" style="font-size:0.82rem;color:var(--muted);">0 pending</span>
    </div>
    <div class="card-body">
      <table>
        <thead><tr><th>Job ID</th><th>Container</th><th>Status</th></tr></thead>
        <tbody id="queue-tbody">
          <tr><td colspan="3"><div class="empty-state" style="padding:32px;"><div class="empty-state-text">Queue empty</div></div></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- TAB: CACHE -->
<div class="tab-content" id="tab-cache">
  <div class="two-col">
    <div class="card">
      <div class="card-header">
        <div class="card-title">⚡ Cache Performance — Mahip's Distributed Cache</div>
      </div>
      <div class="card-body padded">
        <div class="cache-stat-row">
          <span class="cache-stat-label">Cache Hits</span>
          <span class="cache-stat-val" id="cache-hits-val" style="color:var(--green);">0</span>
        </div>
        <div class="cache-stat-row">
          <span class="cache-stat-label">Cache Misses</span>
          <span class="cache-stat-val" id="cache-misses-val" style="color:var(--amber);">0</span>
        </div>
        <div class="cache-stat-row">
          <span class="cache-stat-label">Hit Rate</span>
          <span class="cache-stat-val" id="cache-ratio-val" style="color:var(--cyan);">0%</span>
        </div>
        <div class="cache-stat-row">
          <span class="cache-stat-label">Cache Node</span>
          <span class="cache-stat-val" id="cache-node-val" style="font-size:0.85rem;color:var(--muted);">cache-node-1:8001</span>
        </div>
        <div class="hit-rate-bar">
          <div style="font-size:0.78rem;color:var(--muted);font-weight:500;">Hit Rate</div>
          <div class="hit-rate-track"><div class="hit-rate-fill" id="cache-bar" style="width:0%"></div></div>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div class="card-title">How Caching Works</div>
      </div>
      <div class="card-body padded" style="font-size:0.85rem;line-height:1.8;color:var(--text2);">
        <p><strong>1. Container starts</strong> → SHA-256 hash computed for image layer</p>
        <p style="margin-top:12px;"><strong>2. Cache check</strong> → Query distributed cache node on port 8001</p>
        <p style="margin-top:12px;"><strong>3a. Cache HIT</strong> → Vulnerability data returned instantly, <span style="color:var(--green);font-weight:600;">no Trivy scan needed</span></p>
        <p style="margin-top:12px;"><strong>3b. Cache MISS</strong> → Job enqueued, Trivy scans image, result stored in cache for future hits</p>
        <p style="margin-top:12px;"><strong>Algorithm</strong> → Consistent hashing ring with LRU eviction and 1-hour TTL</p>
      </div>
    </div>
  </div>
</div>

<!-- TAB: AUDIT -->
<div class="tab-content" id="tab-audit">
  <div class="card">
    <div class="card-header">
      <div class="card-title">Audit Log</div>
      <div style="display:flex;align-items:center;gap:12px;">
        <span id="audit-count-tag" style="font-size:0.82rem;color:var(--muted);">0 entries</span>
        <button class="btn-ghost" onclick="clearAudit()">Clear</button>
      </div>
    </div>
    <div class="card-body">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Action</th>
            <th>Container</th>
            <th>Image</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody id="audit-tbody">
          <tr><td colspan="5"><div class="empty-state"><div class="empty-state-text">No audit entries yet</div></div></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────────
let ws = null, events = [], containers = {}, workers = {}, auditLog = [];
let cacheHits = 0, cacheMisses = 0, failovers = 0, totalEvents = 0;
let lastKnownAliveWorkers = 0;
let wsQueueDepthReceived = false;  // true once first WS queue_depth_update arrives
let startTime = Date.now(), reconnectTimer = null;
let activeTab = 'containers';

// ── Tab switching ──────────────────────────────────────────────────────────────
function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  event.currentTarget.classList.add('active');
  if (tab === 'health') setTimeout(drawAllGraphs, 60);
}

// ── Clock ──────────────────────────────────────────────────────────────────────
function updateClock() { document.getElementById('clock').textContent = new Date().toTimeString().slice(0,8); }
setInterval(updateClock, 1000); updateClock();

// ── Failover Banner ────────────────────────────────────────────────────────────
function showFailoverBanner(ev) {
  const existing = document.getElementById('failover-banner');
  if (existing) existing.remove();
  const standbyUrl = 'http://localhost:9090';
  const banner = document.createElement('div');
  banner.id = 'failover-banner'; banner.className = 'failover-banner';
  const left = document.createElement('div'); left.className = 'failover-banner-left';
  const icon = document.createElement('div'); icon.className = 'failover-banner-icon'; icon.textContent = '🚨';
  const text = document.createElement('div');
  const title = document.createElement('div'); title.className = 'failover-banner-title'; title.textContent = 'PRIMARY NODE FAILED — STANDBY PROMOTED';
  const sub = document.createElement('div'); sub.className = 'failover-banner-sub';
  sub.textContent = 'Failover to ' + standbyUrl + ' · Promoted at ' + fmtTime(ev.promoted_at || ev.timestamp);
  text.appendChild(title); text.appendChild(sub); left.appendChild(icon); left.appendChild(text);
  const btn = document.createElement('button'); btn.className = 'failover-banner-btn';
  btn.textContent = '→ Switch to Standby'; btn.onclick = () => window.location.href = standbyUrl;
  banner.appendChild(left); banner.appendChild(btn);
  document.body.insertBefore(banner, document.body.firstChild);
  let countdown = 5;
  const timer = setInterval(() => { countdown--; btn.textContent = '→ Redirecting in ' + countdown + 's...'; if (countdown <= 0) { clearInterval(timer); window.location.href = standbyUrl; } }, 1000);
}

// ── WebSocket ──────────────────────────────────────────────────────────────────
function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto + '://' + location.host + '/ws/dashboard');
  ws.onopen = () => {
    document.getElementById('conn-dot').className = 'conn-dot connected';
    document.getElementById('conn-label').textContent = 'CONNECTED';
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
    pollStatus();
  };
  ws.onmessage = (e) => { handleEvent(JSON.parse(e.data)); };
  ws.onclose = () => {
    document.getElementById('conn-dot').className = 'conn-dot';
    document.getElementById('conn-label').textContent = 'RECONNECTING...';
    if (location.port === '8000') reconnectTimer = setTimeout(checkStandbyAndRedirect, 3000);
    else reconnectTimer = setTimeout(connect, 3000);
  };
  ws.onerror = () => ws.close();
}
connect();

let standbyCheckCount = 0;
async function checkStandbyAndRedirect() {
  standbyCheckCount++;
  try { const r = await fetch('http://localhost:9000/health', { signal: AbortSignal.timeout(2000) }); if (r.ok) { connect(); return; } } catch(e) {}
  try { const r = await fetch('http://localhost:9090/health', { signal: AbortSignal.timeout(2000) }); const data = await r.json(); if (data.is_primary || standbyCheckCount >= 2) { showFailoverBanner({ promoted_at: data.promoted_at }); return; } } catch(e) {}
  if (standbyCheckCount < 5) reconnectTimer = setTimeout(checkStandbyAndRedirect, 2000);
  else connect();
}

// ── Poll ───────────────────────────────────────────────────────────────────────
async function pollStatus() {
  try {
    const s = await fetch('/status').then(r => r.json());
    if (s.containers) { containers = {}; s.containers.forEach(c => containers[c.container_id] = c); renderContainers(); }
    if (s.workers)    { workers = {};    s.workers.forEach(w => workers[w.worker_id || w] = w);     renderWorkers(); }
    // Queue depth comes from WebSocket push (queue_depth_update event)
    // which fires on every enqueue/complete — much faster than this 5s poll.
    // Only use /status value as fallback if no WS update has arrived yet.
    if (s.scan_queue_depth !== undefined && !wsQueueDepthReceived) {
      setEl('m-queue', s.scan_queue_depth);
      setEl('queue-tag', s.scan_queue_depth + ' pending');
      setEl('pipe-queue-sub', s.scan_queue_depth + ' jobs');
    }
  } catch(e) {}
  try { const audit = await fetch('/audit-log').then(r => r.json()); if (Array.isArray(audit)) renderAuditFromApi(audit); } catch(e) {}
  setTimeout(pollStatus, 5000);
}

// ── Event handler ──────────────────────────────────────────────────────────────
function handleEvent(ev) {
  const type = ev.event_type || '';
  const SKIP_COUNT = ['worker_update', 'worker_dead'];
  if (!SKIP_COUNT.includes(type)) {
    totalEvents++;
    setEl('m-events', totalEvents);
    setEl('event-count-tag', totalEvents + ' events');
    setEl('tab-count-events', totalEvents);
    eventCountWindow.push(Date.now());
  }
  // health score update
  applyHealthDelta(type);
  if (type === 'container_start') {
    containers[ev.container_id] = { container_id: ev.container_id, name: ev.container_name, image: ev.image_name, status: 'running' };
    renderContainers(); flashPipe('pipe-queue'); addEvent(ev, 'blue');
  } else if (type === 'container_die') {
    if (containers[ev.container_id]) containers[ev.container_id].status = 'dead';
    renderContainers(); addEvent(ev, 'red');
  } else if (type === 'container_stop' || type === 'container_kill') {
    if (containers[ev.container_id]) containers[ev.container_id].status = 'stopped';
    renderContainers(); addEvent(ev, 'amber');
  } else if (type === 'anomaly_detected') {
    addEvent({ ...ev, event_type: '🚨 ANOMALY: ' + (ev.keyword||'').toUpperCase(), container_name: (ev.container_name||'?') + ' | ' + (ev.log_line||'') }, 'red');
    flashPipe('pipe-failover');
  } else if (type === 'cache_hit') {
    cacheHits++; setEl('m-cache-hits', cacheHits); updateCacheRatio(); addEvent(ev, 'cyan'); flashPipe('pipe-cache');
    // FIX: propagate cached vuln data to container row so it stops showing "scanning..."
    if (ev.container_id && containers[ev.container_id] && ev.vulnerabilities) {
      containers[ev.container_id].vulnerabilities = ev.vulnerabilities;
      containers[ev.container_id].scan_status = 'cache_hit';
      renderContainers();
    } else if (ev.container_id && containers[ev.container_id] && !containers[ev.container_id].vulnerabilities) {
      // fetch from cache node directly
      fetch('http://localhost:9001/cache/' + (ev.layer_hash || '')).then(r => r.ok ? r.json() : null).then(d => {
        if (d && d.vulnerabilities && containers[ev.container_id]) {
          containers[ev.container_id].vulnerabilities = d.vulnerabilities;
          containers[ev.container_id].scan_status = 'cache_hit';
          renderContainers();
        }
      }).catch(() => {});
    }
  } else if (type === 'cache_miss') {
    cacheMisses++; updateCacheRatio(); addEvent(ev, 'amber');
  } else if (type === 'worker_update') {
    const existedBefore = !!workers[ev.worker_id];
    const hadDeadWorkerBefore = Object.values(workers).some(w => (w.status || 'alive') === 'dead');
    const newStatus = ev.status || 'alive';

    workers[ev.worker_id] = {
      worker_id: ev.worker_id,
      status: newStatus,
      load: ev.load || 0,
      jobs_completed: ev.jobs_completed || 0
    };

    renderWorkers();
    if (ev.load > 0) flashPipe('pipe-dispatch');

    /*
      HEALTH FIX:
      When a worker dies, health drops.
      When the scheduler creates/registers a NEW alive worker after that,
      health should recover back to 100 because the system replaced the failed worker.
    */
    if (!existedBefore && hadDeadWorkerBefore && newStatus !== 'dead') {
      setTimeout(() => recoverHealthTo100('Replacement worker alive'), 500);
    }
  } else if (type === 'worker_dead') {
    if (workers[ev.worker_id]) workers[ev.worker_id].status = 'dead';
    renderWorkers(); addEvent(ev, 'red');
  } else if (type === 'auto_failover') {
    failovers++; setEl('m-failovers', failovers); flashPipe('pipe-failover'); addEvent(ev, 'purple');
    // score went down on failure; once replica is created, recover back to full health
    setTimeout(() => recoverHealthTo100('Replica created'), 800);
    if (ev.replica_name) {
      containers[ev.replica_name] = { container_id: ev.replica_name, name: ev.replica_name, image: ev.image||'?', status: 'running', is_replica: true };
      renderContainers();
    }
  } else if (type === 'scan_complete') {
    flashPipe('pipe-scan'); addEvent(ev, 'green');
    if (ev.container_id && containers[ev.container_id]) {
      containers[ev.container_id].vulnerabilities = ev.vulnerabilities;
      containers[ev.container_id].scan_status = ev.status;
      renderContainers();
    }
  } else if (type === 'standby_promoted') {
    showFailoverBanner(ev); addEvent(ev, 'red');
  } else if (type === 'queue_depth_update') {
    const d = ev.queue_depth !== undefined ? ev.queue_depth : 0;
    wsQueueDepthReceived = true;
    setEl('m-queue', d);
    setEl('queue-tag', d + ' pending');
    setEl('pipe-queue-sub', d + ' jobs');
    if (d > 0) flashPipe('pipe-queue');
  } else { addEvent(ev, 'blue'); }

  const running = Object.values(containers).filter(c => c.status === 'running').length;
  setEl('m-running', running);
  const crit = Object.values(containers).filter(c => c.is_critical).length;
  setEl('m-critical', crit);
}

// ── Render Containers ──────────────────────────────────────────────────────────
function renderContainers() {
  const tbody = document.getElementById('container-tbody');
  const list = Object.values(containers);
  setEl('container-count', list.length + ' containers');
  setEl('tab-count-containers', list.length);
  if (!list.length) {
    tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-state-icon">🐳</div><div class="empty-state-text">No containers yet</div></div></td></tr>';
    return;
  }
  tbody.innerHTML = list.map(c => {
    const statusClass = c.status === 'running' ? 'pill-green' : c.status === 'dead' ? 'pill-red' : 'pill-amber';
    const statusPill = '<span class="pill ' + statusClass + '"><span class="dot"></span>' + (c.status||'?') + '</span>';
    const crit = c.is_critical ? '<span class="crit-tag">CRITICAL</span>' : '<span style="color:var(--muted2);">—</span>';
    let vulnsHtml = '<span style="color:var(--muted2);font-size:0.78rem;">scanning...</span>';
    if (c.vulnerabilities) {
      const cv = c.vulnerabilities.CRITICAL || 0;
      const hv = c.vulnerabilities.HIGH || 0;
      vulnsHtml = cv === 0 && hv === 0
        ? '<span class="vuln-badge vuln-ok">✓ Clean</span>'
        : '<span class="vuln-badge vuln-c">' + cv + ' CRIT</span><span class="vuln-badge vuln-h">' + hv + ' HIGH</span>';
    } else if (c.scan_status === 'scan_failed') {
      vulnsHtml = '<span class="vuln-badge vuln-c">Failed</span>';
    }
    return '<tr><td class="mono">' + (c.container_id||'').slice(0,12) + '</td><td style="font-weight:500;">' + (c.name||c.container_name||'?') + (c.is_replica ? ' <span style="font-size:0.68rem;color:var(--purple);background:var(--purple-bg);padding:2px 7px;border-radius:4px;font-weight:600;">REPLICA</span>' : '') + '</td><td class="mono" style="color:var(--muted);">' + trunc(c.image||c.image_name||'?', 28) + '</td><td>' + statusPill + '</td><td>' + vulnsHtml + '</td><td>' + crit + '</td></tr>';
  }).join('');
}

// ── Render Workers ──────────────────────────────────────────────────────────────
function renderWorkers() {
  const grid = document.getElementById('worker-grid');
  const list = Object.values(workers);
  setEl('worker-count-tag', list.length + ' workers');
  setEl('tab-count-workers', list.length);
  setEl('pipe-dispatch-sub', list.length + ' workers');
  if (!list.length) { grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⚙️</div><div class="empty-state-text">No workers registered</div></div>'; return; }
  grid.innerHTML = list.map(w => {
    const id = w.worker_id || w;
    const status = w.status || 'alive';
    const load = w.load || 0;
    const done = w.jobs_completed || 0;
    const isDead = status === 'dead';
    return '<div class="worker-card' + (isDead ? ' dead' : '') + '">' +
      '<div class="worker-id">' + id + '</div>' +
      '<div class="worker-row"><span class="worker-row-label">Status</span><span class="pill ' + (isDead ? 'pill-red' : 'pill-green') + '" style="font-size:0.75rem;padding:3px 10px;"><span class="dot"></span>' + status + '</span></div>' +
      '<div class="worker-row"><span class="worker-row-label">Current Load</span><span class="worker-row-val">' + load + '</span></div>' +
      '<div class="worker-row"><span class="worker-row-label">Jobs Completed</span><span class="worker-row-val">' + done + '</span></div>' +
      '</div>';
  }).join('');
}

// ── Audit Log ──────────────────────────────────────────────────────────────────
function renderAuditFromApi(entries) {
  const tbody = document.getElementById('audit-tbody');
  const recent = entries.slice(-50).reverse();
  setEl('audit-count-tag', entries.length + ' entries');
  setEl('tab-count-audit', entries.length);
  if (!recent.length) { tbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="empty-state-text">No entries yet</div></div></td></tr>'; return; }
  tbody.innerHTML = recent.map(e => {
    const action = e.action || e.event_type || '?';
    const color = action.includes('anomaly') ? 'var(--red)' : action.includes('cache_hit') ? 'var(--cyan)' : action.includes('enqueued') ? 'var(--accent)' : action.includes('failover') ? 'var(--purple)' : 'var(--muted)';
    let detail = '—';
    if (e.log_line) detail = trunc(e.log_line, 60);
    else if (e.job_id) detail = 'job:' + e.job_id.slice(0,8);
    else if (e.layer_hash) detail = 'hash:' + e.layer_hash.slice(0,8);
    return '<tr><td class="mono" style="color:var(--muted);">' + fmtTime(e.timestamp||e.logged_at) + '</td><td class="mono" style="color:' + color + ';font-weight:500;">' + action + '</td><td class="mono">' + (e.container_id||'').slice(0,12) + '</td><td class="mono" style="color:var(--muted);">' + trunc(e.image_name||'—',20) + '</td><td style="font-size:0.78rem;color:var(--muted2);">' + detail + '</td></tr>';
  }).join('');
}
function clearAudit() { document.getElementById('audit-tbody').innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="empty-state-text">Cleared</div></div></td></tr>'; setEl('audit-count-tag','0 entries'); }

// ── Live Events ─────────────────────────────────────────────────────────────────
function addEvent(ev, color) {
  const list = document.getElementById('event-list');
  const empty = list.querySelector('.empty-state');
  if (empty) list.removeChild(empty.closest('.empty-state') || empty);
  const COLORS = {
    blue:   ['var(--accent)',  'var(--accent-bg)',  '#2563eb33'],
    green:  ['var(--green)',   'var(--green-bg)',   '#16a34a33'],
    amber:  ['var(--amber)',   'var(--amber-bg)',   '#d9770633'],
    red:    ['var(--red)',     'var(--red-bg)',     '#dc262633'],
    purple: ['var(--purple)',  'var(--purple-bg)',  '#7c3aed33'],
    cyan:   ['var(--cyan)',    'var(--cyan-bg)',    '#0891b233'],
  };
  const [tc, bg, border] = COLORS[color] || COLORS.blue;
  const type = ev.event_type || 'event';
  const div = document.createElement('div');
  div.className = 'event-row';
  div.style.background = bg; div.style.borderColor = border;
  const badge = document.createElement('span');
  badge.className = 'event-type-badge';
  badge.style.background = border; badge.style.color = tc;
  badge.textContent = type.toUpperCase();
  const detail = document.createElement('div');
  detail.className = 'event-detail-text';
  detail.textContent = (ev.container_name||ev.container_id||'') + (ev.image_name ? ' · ' + trunc(ev.image_name, 32) : '');
  const time = document.createElement('span');
  time.className = 'event-time'; time.textContent = fmtTime(ev.timestamp);
  div.appendChild(time); div.appendChild(badge); div.appendChild(detail);
  list.insertBefore(div, list.firstChild);
  while (list.children.length > 50) list.removeChild(list.lastChild);
}

// ── Cache ──────────────────────────────────────────────────────────────────────
function updateCacheRatio() {
  const total = cacheHits + cacheMisses;
  const ratio = total > 0 ? Math.round((cacheHits / total) * 100) : 0;
  setEl('cache-hits-val', cacheHits); setEl('cache-misses-val', cacheMisses);
  setEl('cache-ratio-val', ratio + '%'); setEl('m-cache-ratio', ratio + '% hit rate');
  setEl('m-cache-hits', cacheHits);
  document.getElementById('cache-bar').style.width = ratio + '%';
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function flashPipe(id) { const el = document.getElementById(id); if(!el) return; el.classList.add('active'); setTimeout(() => el.classList.remove('active'), 2000); }
function setEl(id, val) { const el = document.getElementById(id); if(el) el.textContent = val; }
function fmtTime(iso) { if(!iso) return '--:--:--'; try { return new Date(iso).toTimeString().slice(0,8); } catch { return '?'; } }
function trunc(s, n) { return s && s.length > n ? s.slice(0,n) + '…' : (s||''); }

// ── HEALTH + GRAPH ENGINE ───────────────────────────────────────────────────────
let healthScore = 100;
let healthHistory = [{ t: Date.now(), v: 100, label: null, color: null }];
let loadHistory   = [{ t: Date.now(), v: 0 }];
let rateHistory   = [{ t: Date.now(), v: 0 }];
let eventCountWindow = [];
let healthEventLog = [];
const MAX_PTS = 120;

const SCORE_DELTA = {
  container_start: +2, container_die: -8, container_stop: -5,
  cache_hit: +3, cache_miss: -2, scan_complete: +5,
  auto_failover: -12, failover_recovered: +20,
  worker_dead: -18, anomaly_detected: -15, standby_promoted: -25,
};
const SCORE_LABELS = {
  container_start:'Container started', container_die:'Container died',
  container_stop:'Container stopped', cache_hit:'Cache hit',
  cache_miss:'Cache miss', scan_complete:'Scan complete',
  auto_failover:'Failover triggered', failover_recovered:'Failover recovered',
  worker_dead:'Worker died', anomaly_detected:'Anomaly detected',
  standby_promoted:'Standby promoted',
};

function applyHealthDelta(type, customLabel) {
  const delta = SCORE_DELTA[type] || 0;
  if (delta === 0) return;
  healthScore = Math.max(0, Math.min(100, healthScore + delta));
  const color = delta > 0 ? '#16a34a' : '#dc2626';
  const label = customLabel || SCORE_LABELS[type] || type;
  healthHistory.push({ t: Date.now(), v: healthScore, label, delta, color });
  if (healthHistory.length > MAX_PTS) healthHistory.shift();
  healthEventLog.unshift({ time: new Date().toTimeString().slice(0,8), event: label, delta, score: healthScore });
  if (healthEventLog.length > 100) healthEventLog.pop();
  updateHealthDisplay(); renderHealthEventLog();
}

/*
  This is the important heartbeat/recovery fix.
  Old behavior:
    Worker dies -> health drops and stays low.
  New behavior:
    Worker dies -> health drops.
    Replacement/replica worker appears -> health jumps back to 100.
*/
function recoverHealthTo100(label) {
  if (healthScore >= 100) {
    updateHealthDisplay();
    return;
  }

  const before = healthScore;
  const delta = 100 - before;
  healthScore = 100;

  healthHistory.push({
    t: Date.now(),
    v: healthScore,
    label: label || 'Recovered',
    delta: delta,
    color: '#16a34a'
  });

  if (healthHistory.length > MAX_PTS) healthHistory.shift();

  healthEventLog.unshift({
    time: new Date().toTimeString().slice(0,8),
    event: label || 'Recovered',
    delta: delta,
    score: healthScore
  });

  if (healthEventLog.length > 100) healthEventLog.pop();

  updateHealthDisplay();
  renderHealthEventLog();

  const healthTab = document.getElementById('tab-health');
  if (healthTab && healthTab.classList.contains('active')) {
    drawAllGraphs();
  }
}

function updateHealthDisplay() {
  const el = document.getElementById('health-score-display');
  const badge = document.getElementById('health-status-badge');
  if (!el) return;
  el.textContent = Math.round(healthScore);
  if (healthScore > 70) {
    el.style.color='var(--green)'; badge.style.background='var(--green-bg)'; badge.style.color='var(--green)'; badge.textContent='HEALTHY';
  } else if (healthScore > 40) {
    el.style.color='var(--amber)'; badge.style.background='var(--amber-bg)'; badge.style.color='var(--amber)'; badge.textContent='DEGRADED';
  } else {
    el.style.color='var(--red)'; badge.style.background='var(--red-bg)'; badge.style.color='var(--red)'; badge.textContent='CRITICAL';
  }
}

function resetHealth() {
  healthScore=100; healthHistory=[{t:Date.now(),v:100,label:null}];
  loadHistory=[{t:Date.now(),v:0}]; rateHistory=[{t:Date.now(),v:0}];
  healthEventLog=[]; eventCountWindow=[];
  updateHealthDisplay(); renderHealthEventLog(); drawAllGraphs();
}

function renderHealthEventLog() {
  const tbody = document.getElementById('health-event-tbody');
  if (!tbody) return;
  setEl('health-event-count', healthEventLog.length + ' events');
  if (!healthEventLog.length) { tbody.innerHTML='<tr><td colspan="4"><div class="empty-state"><div class="empty-state-text">No events yet</div></div></td></tr>'; return; }
  tbody.innerHTML = healthEventLog.slice(0,50).map(e => {
    const dc = e.delta>0?'var(--green)':'var(--red)';
    const sc = e.score>70?'var(--green)':e.score>40?'var(--amber)':'var(--red)';
    return '<tr><td class="mono" style="color:var(--muted);">'+e.time+'</td><td>'+e.event+'</td><td style="font-family:var(--mono);font-weight:600;color:'+dc+';">'+(e.delta>0?'+':'')+e.delta+'</td><td style="font-family:var(--mono);font-weight:700;color:'+sc+';">'+Math.round(e.score)+'</td></tr>';
  }).join('');
}

function drawGraph(canvasId, data, opts) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !canvas.offsetWidth) return;
  const dpr = window.devicePixelRatio||1;
  const W = canvas.offsetWidth, H = canvas.offsetHeight||parseInt(canvas.getAttribute('height'))||160;
  canvas.width=W*dpr; canvas.height=H*dpr;
  const ctx = canvas.getContext('2d'); ctx.scale(dpr,dpr);
  ctx.clearRect(0,0,W,H);
  const P={top:14,right:12,bottom:24,left:36};
  const gW=W-P.left-P.right, gH=H-P.top-P.bottom;
  const minV=opts.minV||0, maxV=opts.maxV||100, rng=maxV-minV||1;
  const px=i=>P.left+(data.length<2?gW/2:i/(data.length-1)*gW);
  const py=v=>P.top+gH-((v-minV)/rng)*gH;
  // zones
  if (opts.zones) opts.zones.forEach(z=>{
    ctx.fillStyle=z.color; ctx.fillRect(P.left,py(z.max),gW,py(z.min)-py(z.max));
  });
  // grid
  ctx.strokeStyle='#e2e7ef'; ctx.lineWidth=1;
  [0,25,50,75,100].filter(t=>t>=minV&&t<=maxV).forEach(t=>{
    const y=py(t); ctx.beginPath(); ctx.moveTo(P.left,y); ctx.lineTo(P.left+gW,y); ctx.stroke();
    ctx.fillStyle='#9ca3af'; ctx.font='10px monospace'; ctx.fillText(t,2,y+4);
  });
  if (data.length<2) return;
  // fill
  const grad=ctx.createLinearGradient(0,P.top,0,P.top+gH);
  grad.addColorStop(0,opts.fillTop||'rgba(37,99,235,0.18)'); grad.addColorStop(1,'rgba(255,255,255,0)');
  ctx.beginPath(); ctx.moveTo(px(0),py(data[0].v));
  data.forEach((d,i)=>{ if(i>0) ctx.lineTo(px(i),py(d.v)); });
  ctx.lineTo(px(data.length-1),P.top+gH); ctx.lineTo(px(0),P.top+gH);
  ctx.closePath(); ctx.fillStyle=grad; ctx.fill();
  // line segments
  for(let i=1;i<data.length;i++){
    const v=data[i].v;
    let lc=opts.lineColor||'#2563eb';
    if(opts.dynamicColor) lc=v>70?'#16a34a':v>40?'#d97706':'#dc2626';
    ctx.beginPath(); ctx.moveTo(px(i-1),py(data[i-1].v)); ctx.lineTo(px(i),py(v));
    ctx.strokeStyle=lc; ctx.lineWidth=2.5; ctx.lineJoin='round'; ctx.stroke();
  }
  // event markers
  data.forEach((d,i)=>{
    if(!d.label) return;
    const x=px(i),y=py(d.v);
    ctx.beginPath(); ctx.arc(x,y,5,0,Math.PI*2);
    ctx.fillStyle=d.color||'#7c3aed'; ctx.fill();
    ctx.strokeStyle='#fff'; ctx.lineWidth=1.5; ctx.stroke();
    ctx.fillStyle=d.color||'#7c3aed'; ctx.font='bold 9px sans-serif';
    const tw=ctx.measureText(d.label).width;
    const lx=Math.min(Math.max(x-tw/2,P.left),P.left+gW-tw);
    ctx.fillText(d.label,lx,Math.max(y-9,P.top+9));
  });
  // latest dot
  const ld=data[data.length-1],lx=px(data.length-1),ly=py(ld.v);
  ctx.beginPath(); ctx.arc(lx,ly,4,0,Math.PI*2);
  ctx.fillStyle=opts.dotColor||'#2563eb'; ctx.fill();
}

function drawAllGraphs() {
  drawGraph('healthCanvas', healthHistory, {
    minV:0,maxV:100,dynamicColor:true,fillTop:'rgba(22,163,74,0.12)',
    zones:[{min:70,max:100,color:'rgba(22,163,74,0.04)'},{min:40,max:70,color:'rgba(217,119,6,0.05)'},{min:0,max:40,color:'rgba(220,38,38,0.05)'}]
  });
  drawGraph('loadCanvas', loadHistory, {minV:0,maxV:Math.max(...loadHistory.map(d=>d.v),2),lineColor:'#7c3aed',fillTop:'rgba(124,58,237,0.12)',dotColor:'#7c3aed'});
  drawGraph('rateCanvas', rateHistory, {minV:0,maxV:Math.max(...rateHistory.map(d=>d.v),5),lineColor:'#0891b2',fillTop:'rgba(8,145,178,0.12)',dotColor:'#0891b2'});
}

// 1-second ticker
setInterval(()=>{
  const now=Date.now();
  if(!healthHistory.length||now-healthHistory[healthHistory.length-1].t>1400){
    healthHistory.push({t:now,v:healthScore,label:null});
    if(healthHistory.length>MAX_PTS) healthHistory.shift();
  }
  eventCountWindow=eventCountWindow.filter(t=>now-t<60000);
  const rate=eventCountWindow.length;
  rateHistory.push({t:now,v:rate}); if(rateHistory.length>MAX_PTS) rateHistory.shift();
  setEl('event-rate-label',rate+' events/min');
  const totalLoad=Object.values(workers).reduce((s,w)=>s+(w.load||0),0);

  // Backup recovery check:
  // If dashboard has dead workers, but at least one alive replacement is now present,
  // recover the health score back to 100 even if the recovery came from /status polling.
  const workerList = Object.values(workers);
  const aliveWorkers = workerList.filter(w => (w.status || 'alive') !== 'dead').length;
  const deadWorkers = workerList.filter(w => (w.status || 'alive') === 'dead').length;
  if (deadWorkers > 0 && aliveWorkers > lastKnownAliveWorkers && healthScore < 100) {
    recoverHealthTo100('Replacement worker alive');
  }
  lastKnownAliveWorkers = aliveWorkers;

  loadHistory.push({t:now,v:totalLoad}); if(loadHistory.length>MAX_PTS) loadHistory.shift();
  setEl('worker-load-label',totalLoad+' active jobs');
  const healthTab=document.getElementById('tab-health');
  if(healthTab&&healthTab.classList.contains('active')) drawAllGraphs();
},1000);

window.addEventListener('resize',()=>{
  const healthTab=document.getElementById('tab-health');
  if(healthTab&&healthTab.classList.contains('active')) drawAllGraphs();
});

</script>

<!-- TAB: HEALTH -->
<div class="tab-content" id="tab-health">
  <div class="two-col" style="margin-bottom:20px;">
    <div class="card" style="grid-column:1/3;">
      <div class="card-header">
        <div class="card-title">System Health Score &mdash; Live</div>
        <div style="display:flex;align-items:center;gap:16px;">
          <span id="health-score-display" style="font-family:var(--mono);font-size:1.4rem;font-weight:700;color:var(--green);">100</span>
          <span style="font-size:0.78rem;color:var(--muted);">/ 100</span>
          <span id="health-status-badge" style="font-size:0.72rem;font-weight:600;padding:3px 12px;border-radius:100px;background:var(--green-bg);color:var(--green);">HEALTHY</span>
          <button class="btn-ghost" onclick="resetHealth()">Reset</button>
        </div>
      </div>
      <div class="card-body padded" style="padding-top:8px;">
        <canvas id="healthCanvas" height="160" style="width:100%;display:block;cursor:crosshair;"></canvas>
        <div style="display:flex;gap:20px;margin-top:10px;flex-wrap:wrap;">
          <span style="font-size:0.72rem;color:var(--green);">Healthy (&gt;70)</span>
          <span style="font-size:0.72rem;color:var(--amber);">Degraded (40-70)</span>
          <span style="font-size:0.72rem;color:var(--red);">Critical (&lt;40)</span>
        </div>
      </div>
    </div>
  </div>
  <div class="two-col">
    <div class="card">
      <div class="card-header">
        <div class="card-title">Worker Load &mdash; Live</div>
        <span style="font-size:0.78rem;color:var(--muted);" id="worker-load-label">0 active jobs</span>
      </div>
      <div class="card-body padded" style="padding-top:8px;">
        <canvas id="loadCanvas" height="120" style="width:100%;display:block;"></canvas>
        <div style="font-size:0.72rem;color:var(--muted);margin-top:8px;">Combined job load across all workers</div>
      </div>
    </div>
    <div class="card">
      <div class="card-header">
        <div class="card-title">Event Rate &mdash; Live</div>
        <span style="font-size:0.78rem;color:var(--muted);" id="event-rate-label">0 events/min</span>
      </div>
      <div class="card-body padded" style="padding-top:8px;">
        <canvas id="rateCanvas" height="120" style="width:100%;display:block;"></canvas>
        <div style="font-size:0.72rem;color:var(--muted);margin-top:8px;">Docker events per minute</div>
      </div>
    </div>
  </div>
  <div class="card" style="margin-top:20px;">
    <div class="card-header">
      <div class="card-title">Health Event Log</div>
      <span style="font-size:0.78rem;color:var(--muted);" id="health-event-count">0 events</span>
    </div>
    <div class="card-body">
      <table>
        <thead><tr><th>Time</th><th>Event</th><th>Score Impact</th><th>Score After</th></tr></thead>
        <tbody id="health-event-tbody">
          <tr><td colspan="4"><div class="empty-state"><div class="empty-state-text">Health events will appear here</div></div></td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

</body>
</html>"""