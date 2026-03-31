DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Resilient Container Security Engine</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

  :root {
    --bg:       #070b14;
    --surface:  #0c1220;
    --card:     #101828;
    --border:   #1a2540;
    --border2:  #243050;
    --accent:   #3b82f6;
    --green:    #10b981;
    --amber:    #f59e0b;
    --red:      #ef4444;
    --purple:   #8b5cf6;
    --cyan:     #06b6d4;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --muted2:   #94a3b8;
    --mono:     'JetBrains Mono', monospace;
    --sans:     'Inter', sans-serif;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: var(--sans); background: var(--bg); color: var(--text); min-height: 100vh; }

  /* TOPBAR */
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 28px; height: 56px;
    background: var(--surface); border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 100;
  }
  .topbar-left { display: flex; align-items: center; gap: 14px; }
  .logo { font-family: var(--mono); font-size: 0.82rem; font-weight: 700; color: var(--accent); letter-spacing: 0.05em; }
  .logo span { color: var(--muted2); font-weight: 400; }
  .tag { font-family: var(--mono); font-size: 0.65rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; letter-spacing: 0.06em; }
  .tag-blue   { background: rgba(59,130,246,0.15);  color: #93c5fd; border: 1px solid rgba(59,130,246,0.25); }
  .tag-green  { background: rgba(16,185,129,0.12);  color: #6ee7b7; border: 1px solid rgba(16,185,129,0.22); }
  .tag-amber  { background: rgba(245,158,11,0.12);  color: #fcd34d; border: 1px solid rgba(245,158,11,0.22); }
  .tag-red    { background: rgba(239,68,68,0.12);   color: #fca5a5; border: 1px solid rgba(239,68,68,0.22); }
  .tag-purple { background: rgba(139,92,246,0.12);  color: #c4b5fd; border: 1px solid rgba(139,92,246,0.22); }
  .tag-cyan   { background: rgba(6,182,212,0.12);   color: #67e8f9; border: 1px solid rgba(6,182,212,0.22); }
  .topbar-right { display: flex; align-items: center; gap: 12px; }
  .conn-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--red); transition: background 0.3s; box-shadow: 0 0 6px currentColor; }
  .conn-dot.connected { background: var(--green); }
  .conn-label { font-size: 0.72rem; color: var(--muted2); font-family: var(--mono); }
  .clock { font-family: var(--mono); font-size: 0.72rem; color: var(--muted); }

  /* LAYOUT */
  .main { padding: 20px 28px 40px; }

  /* METRICS */
  .metrics { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 20px; }
  .metric { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; position: relative; overflow: hidden; }
  .metric::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px; }
  .metric.blue::after   { background: var(--accent); }
  .metric.green::after  { background: var(--green);  }
  .metric.amber::after  { background: var(--amber);  }
  .metric.red::after    { background: var(--red);    }
  .metric.purple::after { background: var(--purple); }
  .metric.cyan::after   { background: var(--cyan);   }
  .metric-label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; margin-bottom: 6px; }
  .metric-value { font-family: var(--mono); font-size: 1.6rem; font-weight: 700; line-height: 1; color: var(--text); transition: color 0.3s; }
  .metric-sub { font-size: 0.65rem; color: var(--muted); margin-top: 4px; }

  /* GRID */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px; }

  /* PANEL */
  .panel { background: var(--card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
  .panel-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border); background: var(--surface); }
  .panel-title { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted2); display: flex; align-items: center; gap: 8px; }
  .panel-body { padding: 12px; max-height: 320px; overflow-y: auto; }
  .panel-body::-webkit-scrollbar { width: 4px; }
  .panel-body::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

  /* TABLE */
  table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
  th { text-align: left; padding: 6px 10px; color: var(--muted); font-weight: 600; font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.06em; border-bottom: 1px solid var(--border); }
  td { padding: 7px 10px; border-bottom: 1px solid rgba(26,37,64,0.5); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(59,130,246,0.03); }
  .mono { font-family: var(--mono); font-size: 0.72rem; }
  .status-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
  .dot-green  { background: var(--green);  box-shadow: 0 0 5px var(--green); }
  .dot-red    { background: var(--red);    box-shadow: 0 0 5px var(--red); }
  .dot-amber  { background: var(--amber);  box-shadow: 0 0 5px var(--amber); }
  .dot-grey   { background: var(--muted); }

  /* EVENT FEED */
  .event-list { display: flex; flex-direction: column; gap: 6px; }
  .event-item { display: flex; align-items: flex-start; gap: 10px; padding: 8px 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; font-size: 0.73rem; animation: slideIn 0.25s ease; }
  @keyframes slideIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
  .event-time { font-family: var(--mono); font-size: 0.65rem; color: var(--muted); white-space: nowrap; padding-top: 1px; }
  .event-body { flex: 1; }
  .event-type { font-family: var(--mono); font-size: 0.68rem; font-weight: 700; margin-bottom: 2px; }
  .event-detail { color: var(--muted2); font-size: 0.68rem; }

  /* CACHE BAR */
  .cache-bar-wrap { background: var(--surface); border-radius: 6px; overflow: hidden; height: 8px; margin-top: 8px; }
  .cache-bar-fill { height: 100%; background: linear-gradient(90deg, var(--green), var(--cyan)); border-radius: 6px; transition: width 0.6s ease; }

  /* WORKER CARD */
  .worker-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 12px; }
  .worker-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
  .worker-name { font-family: var(--mono); font-size: 0.75rem; font-weight: 700; margin-bottom: 6px; }
  .worker-stat { font-size: 0.68rem; color: var(--muted2); display: flex; justify-content: space-between; margin-top: 3px; }
  .worker-stat span { color: var(--text); font-family: var(--mono); }

  /* PIPELINE */
  .pipeline { display: flex; align-items: center; gap: 0; padding: 16px; background: var(--surface); border-bottom: 1px solid var(--border); overflow-x: auto; }
  .pipe-step { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 90px; }
  .pipe-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 1rem; position: relative; }
  .pipe-icon.active::after { content: ''; position: absolute; inset: -3px; border-radius: 10px; border: 2px solid currentColor; opacity: 0.4; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%, 100% { opacity: 0.4; transform: scale(1); } 50% { opacity: 0.1; transform: scale(1.1); } }
  .pipe-icon.blue   { background: rgba(59,130,246,0.15); color: var(--accent); }
  .pipe-icon.green  { background: rgba(16,185,129,0.15); color: var(--green); }
  .pipe-icon.amber  { background: rgba(245,158,11,0.15); color: var(--amber); }
  .pipe-icon.purple { background: rgba(139,92,246,0.15); color: var(--purple); }
  .pipe-icon.cyan   { background: rgba(6,182,212,0.15);  color: var(--cyan); }
  .pipe-label { font-size: 0.62rem; color: var(--muted2); text-align: center; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
  .pipe-sublabel { font-family: var(--mono); font-size: 0.6rem; color: var(--muted); text-align: center; }
  .pipe-arrow { font-size: 1rem; color: var(--border2); padding: 0 6px; flex-shrink: 0; padding-bottom: 16px; }

  /* EMPTY */
  .empty { text-align: center; padding: 32px; color: var(--muted); font-size: 0.78rem; }
  .empty-icon { font-size: 2rem; margin-bottom: 8px; opacity: 0.4; }

  /* FOOTER */
  .footer { border-top: 1px solid var(--border); padding: 10px 28px; display: flex; justify-content: space-between; align-items: center; font-family: var(--mono); font-size: 0.63rem; color: var(--muted); }
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <div class="logo">RCSCE <span>/ master-node</span></div>
    <span class="tag tag-blue">Phase 5</span>
    <span class="tag tag-green">Control Plane</span>
    <span class="tag tag-purple">AOS · TAMU-CC</span>
  </div>
  <div class="topbar-right">
    <span class="clock" id="clock">--:--:--</span>
    <span class="conn-dot" id="conn-dot"></span>
    <span class="conn-label" id="conn-label">DISCONNECTED</span>
  </div>
</div>

<!-- PIPELINE -->
<div class="panel" style="margin:16px 28px 0;border-radius:12px 12px 0 0;">
  <div class="pipeline">
    <div class="pipe-step">
      <div class="pipe-icon blue active" id="pipe-docker">🐳</div>
      <div class="pipe-label">Docker</div>
      <div class="pipe-sublabel" id="pipe-docker-sub">listening</div>
    </div>
    <div class="pipe-arrow">→</div>
    <div class="pipe-step">
      <div class="pipe-icon blue" id="pipe-listener">📡</div>
      <div class="pipe-label">Listener</div>
      <div class="pipe-sublabel" id="pipe-listener-sub">events</div>
    </div>
    <div class="pipe-arrow">→</div>
    <div class="pipe-step">
      <div class="pipe-icon cyan" id="pipe-cache">⚡</div>
      <div class="pipe-label">Cache</div>
      <div class="pipe-sublabel" id="pipe-cache-sub">check</div>
    </div>
    <div class="pipe-arrow">→</div>
    <div class="pipe-step">
      <div class="pipe-icon amber" id="pipe-queue">📋</div>
      <div class="pipe-label">Queue</div>
      <div class="pipe-sublabel" id="pipe-queue-sub">0 jobs</div>
    </div>
    <div class="pipe-arrow">→</div>
    <div class="pipe-step">
      <div class="pipe-icon purple" id="pipe-dispatch">⚙️</div>
      <div class="pipe-label">Dispatch</div>
      <div class="pipe-sublabel" id="pipe-dispatch-sub">workers</div>
    </div>
    <div class="pipe-arrow">→</div>
    <div class="pipe-step">
      <div class="pipe-icon green" id="pipe-scan">🔍</div>
      <div class="pipe-label">Scan</div>
      <div class="pipe-sublabel" id="pipe-scan-sub">Trivy</div>
    </div>
    <div class="pipe-arrow">→</div>
    <div class="pipe-step">
      <div class="pipe-icon green" id="pipe-failover">🛡️</div>
      <div class="pipe-label">Failover</div>
      <div class="pipe-sublabel" id="pipe-failover-sub">resilience</div>
    </div>
  </div>
</div>

<div class="main" style="padding-top:16px;">

  <!-- METRICS -->
  <div class="metrics">
    <div class="metric blue">
      <div class="metric-label">Total Events</div>
      <div class="metric-value" id="m-events">0</div>
      <div class="metric-sub">since startup</div>
    </div>
    <div class="metric green">
      <div class="metric-label">Running</div>
      <div class="metric-value" id="m-running">0</div>
      <div class="metric-sub">containers</div>
    </div>
    <div class="metric amber">
      <div class="metric-label">Queue Depth</div>
      <div class="metric-value" id="m-queue">0</div>
      <div class="metric-sub">pending jobs</div>
    </div>
    <div class="metric cyan">
      <div class="metric-label">Cache Hits</div>
      <div class="metric-value" id="m-cache-hits">0</div>
      <div class="metric-sub" id="m-cache-ratio">0% hit rate</div>
    </div>
    <div class="metric red">
      <div class="metric-label">Auto-Failovers</div>
      <div class="metric-value" id="m-failovers">0</div>
      <div class="metric-sub">replicas spun up</div>
    </div>
    <div class="metric purple">
      <div class="metric-label">Critical</div>
      <div class="metric-value" id="m-critical">0</div>
      <div class="metric-sub">marked containers</div>
    </div>
  </div>

  <!-- ROW 1: Containers + Events -->
  <div class="grid-2">
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">🐳 Active Containers</div>
        <span class="tag tag-green" id="container-count">0</span>
      </div>
      <div class="panel-body" style="padding:0;">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Image</th><th>Status</th><th>Critical</th></tr></thead>
          <tbody id="container-tbody">
            <tr><td colspan="5" class="empty"><div class="empty-icon">🐳</div>No containers yet</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">📡 Live Event Feed</div>
        <span class="tag tag-blue" id="event-count-tag">0 events</span>
      </div>
      <div class="panel-body">
        <div class="event-list" id="event-list">
          <div class="empty"><div class="empty-icon">📡</div>Waiting for Docker events...</div>
        </div>
      </div>
    </div>
  </div>

  <!-- ROW 2: Workers + Cache + Queue -->
  <div class="grid-3">
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">⚙️ Workers</div>
        <span class="tag tag-purple" id="worker-count-tag">0 workers</span>
      </div>
      <div class="worker-grid" id="worker-grid">
        <div class="empty" style="grid-column:1/-1"><div class="empty-icon">⚙️</div>No workers registered</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">⚡ Cache Performance</div>
        <span class="tag tag-cyan">Mahip's Cache</span>
      </div>
      <div class="panel-body">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
          <span style="font-size:0.72rem;color:var(--muted2)">Hits</span>
          <span class="mono" id="cache-hits-val" style="color:var(--green)">0</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
          <span style="font-size:0.72rem;color:var(--muted2)">Misses</span>
          <span class="mono" id="cache-misses-val" style="color:var(--amber)">0</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <span style="font-size:0.72rem;color:var(--muted2)">Hit Rate</span>
          <span class="mono" id="cache-ratio-val" style="color:var(--cyan)">0%</span>
        </div>
        <div class="cache-bar-wrap"><div class="cache-bar-fill" id="cache-bar" style="width:0%"></div></div>
        <div style="margin-top:14px;display:flex;justify-content:space-between;">
          <span style="font-size:0.72rem;color:var(--muted2)">Cache Entries</span>
          <span class="mono" id="cache-entries-val">0</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:6px;">
          <span style="font-size:0.72rem;color:var(--muted2)">Node</span>
          <span class="mono" style="color:var(--purple)" id="cache-node-val">—</span>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">📋 Scan Queue</div>
        <span class="tag tag-amber" id="queue-tag">0 pending</span>
      </div>
      <div class="panel-body" style="padding:0;">
        <table>
          <thead><tr><th>Job ID</th><th>Container</th><th>Status</th></tr></thead>
          <tbody id="queue-tbody">
            <tr><td colspan="3" class="empty">Queue empty</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ROW 3: Audit Log -->
  <div class="panel">
    <div class="panel-header">
      <div class="panel-title">📜 Audit Log</div>
      <div style="display:flex;gap:8px;">
        <span class="tag tag-blue" id="audit-count-tag">0 entries</span>
        <button onclick="clearAudit()" style="font-size:0.65rem;background:none;border:1px solid var(--border2);color:var(--muted);padding:2px 8px;border-radius:4px;cursor:pointer;">Clear</button>
      </div>
    </div>
    <div class="panel-body" style="max-height:200px;">
      <table>
        <thead><tr><th>Time</th><th>Action</th><th>Container</th><th>Image</th><th>Detail</th></tr></thead>
        <tbody id="audit-tbody">
          <tr><td colspan="5" class="empty">No audit entries yet</td></tr>
        </tbody>
      </table>
    </div>
  </div>

</div>

<div class="footer">
  <span>Resilient Container Security &amp; Compliance Engine · Code Gems · TAMU-CC AOS</span>
  <span id="footer-stats">Events: 0 | Uptime: 0s</span>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────────
let ws = null, events = [], containers = {}, workers = {}, auditLog = [];
let cacheHits = 0, cacheMisses = 0, failovers = 0, totalEvents = 0;
let startTime = Date.now(), reconnectTimer = null;

// ── Clock ──────────────────────────────────────────────────────────────────────
function updateClock() { document.getElementById('clock').textContent = new Date().toTimeString().slice(0,8); }
setInterval(updateClock, 1000); updateClock();

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
    reconnectTimer = setTimeout(connect, 3000);
  };
  ws.onerror = () => ws.close();
}
connect();

// ── Poll /status + /audit-log every 5 s ───────────────────────────────────────
async function pollStatus() {
  try {
    const s = await fetch('/status').then(r => r.json());
    if (s.containers) { containers = {}; s.containers.forEach(c => containers[c.container_id] = c); renderContainers(); }
    if (s.workers)    { workers = {};    s.workers.forEach(w => workers[w.worker_id || w] = w);     renderWorkers(); }
    if (s.scan_queue_depth !== undefined) {
      setEl('m-queue', s.scan_queue_depth);
      setEl('queue-tag', s.scan_queue_depth + ' pending');
      setEl('pipe-queue-sub', s.scan_queue_depth + ' jobs');
    }
  } catch(e) {}
  try {
    const audit = await fetch('/audit-log').then(r => r.json());
    if (Array.isArray(audit)) renderAuditFromApi(audit);
  } catch(e) {}
  setTimeout(pollStatus, 5000);
}

// ── Event handler ──────────────────────────────────────────────────────────────
function handleEvent(ev) {
  totalEvents++;
  setEl('m-events', totalEvents);
  setEl('event-count-tag', totalEvents + ' events');
  const type = ev.event_type || '';

  if (type === 'container_start') {
    containers[ev.container_id] = { container_id: ev.container_id, name: ev.container_name, image: ev.image_name, status: 'running' };
    renderContainers(); flashPipe('pipe-queue'); addEvent(ev, 'blue');
  } else if (type === 'container_die') {
    if (containers[ev.container_id]) containers[ev.container_id].status = 'dead';
    renderContainers(); failovers++; setEl('m-failovers', failovers); addEvent(ev, 'red'); flashPipe('pipe-failover');
  } else if (type === 'container_stop' || type === 'container_kill') {
    if (containers[ev.container_id]) containers[ev.container_id].status = 'stopped';
    renderContainers(); addEvent(ev, 'amber');
  } else if (type === 'anomaly_detected') {
    // 🚨 NEW: Explicitly handle the anomalies in bright red!
    addEvent({
      ...ev,
      event_type: '🚨 ANOMALY: ' + (ev.keyword ? ev.keyword.toUpperCase() : 'ERROR'),
      container_name: (ev.container_name || '?') + ' | ' + (ev.log_line || '')
    }, 'red');
    flashPipe('pipe-failover');
  } else if (type === 'cache_hit') {
    cacheHits++; setEl('m-cache-hits', cacheHits); updateCacheRatio(); addEvent(ev, 'cyan'); flashPipe('pipe-cache');
  } else if (type === 'cache_miss') {
    cacheMisses++; updateCacheRatio(); addEvent(ev, 'amber');
  } else if (type === 'worker_update') {
    workers[ev.worker_id] = { worker_id: ev.worker_id, status: ev.status, load: ev.load };
    renderWorkers();
    if (ev.load > 0) flashPipe('pipe-dispatch');
  } else if (type === 'worker_dead') {
    if (workers[ev.worker_id]) workers[ev.worker_id].status = 'dead';
    renderWorkers();
    addEvent(ev, 'red');
  } else if (type === 'scan_complete') {
    flashPipe('pipe-scan');
    addEvent(ev, 'green');
  } else if (type === 'standby_promoted') {
    showFailoverBanner(ev);
    addEvent(ev, 'red');
  } else { 
    addEvent(ev, 'blue'); 
  }

  const running = Object.values(containers).filter(c => c.status === 'running').length;
  setEl('m-running', running);
  const crit = Object.values(containers).filter(c => c.is_critical).length;
  setEl('m-critical', crit);
  const uptime = Math.floor((Date.now() - startTime) / 1000);
  setEl('footer-stats', 'Events: ' + totalEvents + ' | Uptime: ' + uptime + 's');
}

// ── Render Containers ──────────────────────────────────────────────────────────
function renderContainers() {
  const tbody = document.getElementById('container-tbody');
  const list = Object.values(containers);
  setEl('container-count', list.length);
  if (!list.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty"><div class="empty-icon">🐳</div>No containers yet</td></tr>'; return; }
  tbody.innerHTML = list.map(c => {
    const dc = c.status === 'running' ? 'dot-green' : c.status === 'dead' ? 'dot-red' : c.status === 'stopped' ? 'dot-amber' : 'dot-grey';
    const crit = c.is_critical ? '<span class="tag tag-red">CRITICAL</span>' : '<span style="color:var(--muted);font-size:0.65rem">—</span>';
    return '<tr><td class="mono">' + (c.container_id||'').slice(0,12) + '</td><td>' + (c.name||c.container_name||'?') + '</td><td class="mono" style="color:var(--muted2)">' + trunc(c.image||c.image_name||'?',24) + '</td><td><span class="status-dot ' + dc + '"></span>' + (c.status||'?') + '</td><td>' + crit + '</td></tr>';
  }).join('');
}

// ── Render Workers ─────────────────────────────────────────────────────────────
function renderWorkers() {
  const grid = document.getElementById('worker-grid');
  const list = Object.values(workers);
  setEl('worker-count-tag', list.length + ' workers');
  setEl('pipe-dispatch-sub', list.length + ' workers');
  if (!list.length) { grid.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="empty-icon">⚙️</div>No workers registered</div>'; return; }
  grid.innerHTML = list.map(w => {
    const id = w.worker_id || w, status = w.status || 'alive', load = w.load || 0;
    const dc = status === 'alive' ? 'dot-green' : 'dot-red';
    return '<div class="worker-card"><div class="worker-name"><span class="status-dot ' + dc + '"></span>' + id + '</div><div class="worker-stat">Status <span>' + status + '</span></div><div class="worker-stat">Load <span>' + load + '</span></div></div>';
  }).join('');
}

// ── Audit Log ──────────────────────────────────────────────────────────────────
function renderAuditFromApi(entries) {
  const tbody = document.getElementById('audit-tbody');
  const recent = entries.slice(-50).reverse();
  setEl('audit-count-tag', entries.length + ' entries');
  if (!recent.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty">No audit entries yet</td></tr>'; return; }
  tbody.innerHTML = recent.map(e => {
    const action = e.action || e.event_type || '?';
    // Color anomalies red
    const color = action.includes('anomaly') ? 'var(--red)' : action.includes('cache_hit') ? 'var(--cyan)' : action.includes('enqueued') ? 'var(--accent)' : action.includes('failover') ? 'var(--purple)' : action.includes('died') ? 'var(--red)' : 'var(--muted2)';
    
    // Check if it's an anomaly and display the log line, otherwise show job/hash
    let detail = '—';
    if (e.log_line) { detail = trunc(e.log_line, 60); }
    else if (e.job_id) { detail = 'job:' + e.job_id.slice(0,8); }
    else if (e.layer_hash) { detail = 'hash:' + e.layer_hash.slice(0,8); }
    
    return '<tr><td class="mono" style="color:var(--muted)">' + fmtTime(e.timestamp||e.logged_at) + '</td><td class="mono" style="color:' + color + '">' + action + '</td><td class="mono">' + (e.container_id||'').slice(0,12) + '</td><td class="mono" style="color:var(--muted2)">' + trunc(e.image_name||'—',20) + '</td><td style="color:var(--muted);font-size:0.65rem">' + detail + '</td></tr>';
  }).join('');
}

function clearAudit() { document.getElementById('audit-tbody').innerHTML = '<tr><td colspan="5" class="empty">Cleared</td></tr>'; setEl('audit-count-tag','0 entries'); }

// ── Live Event Feed ────────────────────────────────────────────────────────────
function addEvent(ev, color) {
  const list = document.getElementById('event-list');
  const empty = list.querySelector('.empty');
  if (empty) empty.parentElement.removeChild(empty);
  const COLORS = { blue:['var(--accent)','rgba(59,130,246,0.08)'], green:['var(--green)','rgba(16,185,129,0.08)'], amber:['var(--amber)','rgba(245,158,11,0.08)'], red:['var(--red)','rgba(239,68,68,0.08)'], purple:['var(--purple)','rgba(139,92,246,0.08)'], cyan:['var(--cyan)','rgba(6,182,212,0.08)'] };
  const [tc, bg] = COLORS[color] || COLORS.blue;
  const type = ev.event_type || ev.type || 'event';
  const div = document.createElement('div');
  div.className = 'event-item';
  div.style.background = bg; div.style.borderColor = tc + '33';
  div.innerHTML = '<div class="event-time">' + fmtTime(ev.timestamp) + '</div><div class="event-body"><div class="event-type" style="color:' + tc + '">' + type.toUpperCase() + '</div><div class="event-detail">' + (ev.container_name||ev.container_id||'') + (ev.image_name ? ' · ' + trunc(ev.image_name,30) : '') + '</div></div>';
  list.insertBefore(div, list.firstChild);
  while (list.children.length > 40) list.removeChild(list.lastChild);
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
</script>
</body>
</html>"""
