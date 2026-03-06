DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Container Security Engine</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:#0f1117;color:#e2e8f0}
    header{background:#1a1f2e;padding:16px 24px;border-bottom:1px solid #2d3748;display:flex;align-items:center;gap:12px}
    header h1{font-size:1.2rem;font-weight:600;color:#63b3ed}
    .badge{font-size:.7rem;padding:2px 8px;border-radius:9999px;background:#22543d;color:#68d391;font-weight:600}
    main{padding:24px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
    .card{background:#1a1f2e;border-radius:10px;padding:20px;border:1px solid #2d3748}
    .card h2{font-size:.85rem;text-transform:uppercase;letter-spacing:.05em;color:#90cdf4;margin-bottom:14px}
    table{width:100%;border-collapse:collapse;font-size:.85rem}
    th{text-align:left;padding:8px 10px;color:#718096;border-bottom:1px solid #2d3748;font-weight:500}
    td{padding:8px 10px;border-bottom:1px solid #1e2533}
    .run{color:#68d391;font-weight:600}.dead{color:#fc8181;font-weight:600}.crit{color:#f6ad55;font-weight:600}
    #feed{max-height:340px;overflow-y:auto;font-size:.8rem}
    .erow{padding:6px 8px;border-bottom:1px solid #1e2533;display:flex;gap:10px;align-items:flex-start}
    .etype{font-weight:600;color:#63b3ed;min-width:140px}
    .etime{color:#4a5568;font-size:.75rem;margin-left:auto;white-space:nowrap}
    .mg{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
    .m{background:#161b27;border-radius:8px;padding:14px;text-align:center}
    .mv{font-size:2rem;font-weight:700;color:#63b3ed}
    .ml{font-size:.75rem;color:#718096;margin-top:4px}
    .dot{width:8px;height:8px;border-radius:50%;background:#fc8181;display:inline-block}
    .dot.on{background:#68d391}
  </style>
</head>
<body>
<header>
  <div><h1>&#x1F6E1; Resilient Container Security Engine</h1>
  <small style="color:#718096">Control Plane Dashboard &mdash; Live</small></div>
  <span class="badge">MASTER NODE</span>
  <span style="margin-left:auto;display:flex;align-items:center;gap:6px;font-size:.8rem;color:#718096">
    <span class="dot" id="dot"></span><span id="wslabel">Connecting...</span>
  </span>
</header>
<main>
  <div class="card" style="grid-column:1/-1">
    <h2>Active Containers</h2>
    <table><thead><tr><th>ID</th><th>Name</th><th>Image</th><th>Status</th><th>Critical</th><th>Updated</th></tr></thead>
    <tbody id="ctbl"><tr><td colspan="6" style="color:#4a5568;text-align:center;padding:20px">Waiting for events...</td></tr></tbody></table>
  </div>
  <div class="card"><h2>Live Event Feed</h2><div id="feed"></div></div>
  <div class="card"><h2>Metrics</h2>
    <div class="mg">
      <div class="m"><div class="mv" id="mtot">0</div><div class="ml">Total Events</div></div>
      <div class="m"><div class="mv" id="mfo">0</div><div class="ml">Auto-Failovers</div></div>
      <div class="m"><div class="mv" id="mrun">0</div><div class="ml">Running</div></div>
      <div class="m"><div class="mv" id="mcrit">0</div><div class="ml">Critical</div></div>
    </div>
  </div>
</main>
<script>
const containers={};let total=0,fo=0;
const ws=new WebSocket(`ws://${location.host}/ws/dashboard`);
const dot=document.getElementById('dot'),lbl=document.getElementById('wslabel');
ws.onopen=()=>{dot.classList.add('on');lbl.textContent='Connected'};
ws.onclose=()=>{dot.classList.remove('on');lbl.textContent='Disconnected'};
ws.onmessage=(m)=>{
  const e=JSON.parse(m.data);total++;
  document.getElementById('mtot').textContent=total;
  if(e.container_id){
    containers[e.container_id]=containers[e.container_id]||{};
    Object.assign(containers[e.container_id],{
      container_id:e.container_id,
      name:e.container_name||e.name||'—',
      image:e.image_name||e.image||'—',
      status:e.event_type==='container_start'?'running':e.event_type==='container_die'?'dead':'unknown',
      is_critical:e.is_critical||false,
      updated_at:e.timestamp
    });
    render();
  }
  if(e.event_type==='auto_failover'){fo++;document.getElementById('mfo').textContent=fo;}
  addRow(e);
};
function render(){
  const tbody=document.getElementById('ctbl');
  const r=Object.values(containers).map(c=>{
    const sc=c.status==='running'?'run':c.status==='dead'?'dead':'';
    return`<tr><td><code>${c.container_id}</code></td><td>${c.name}</td><td>${c.image}</td>
    <td class="${sc}">${c.status}</td>
    <td>${c.is_critical?'<span class="crit">YES</span>':'no'}</td>
    <td style="color:#4a5568;font-size:.75rem">${c.updated_at||''}</td></tr>`;
  });
  tbody.innerHTML=r.length?r.join(''):'<tr><td colspan="6" style="color:#4a5568;text-align:center;padding:20px">No containers yet</td></tr>';
  document.getElementById('mrun').textContent=Object.values(containers).filter(c=>c.status==='running').length;
  document.getElementById('mcrit').textContent=Object.values(containers).filter(c=>c.is_critical).length;
}
function addRow(e){
  const feed=document.getElementById('feed');
  const row=document.createElement('div');row.className='erow';
  const t=new Date(e.timestamp||Date.now()).toLocaleTimeString();
  row.innerHTML=`<span class="etype">${e.event_type||'event'}</span><span>${e.container_name||e.replica_name||'—'}</span><span class="etime">${t}</span>`;
  feed.prepend(row);
  if(feed.children.length>100)feed.removeChild(feed.lastChild);
}
</script>
</body></html>"""
