/**
 * Canvas rendering — nodes e edges SVG.
 */
let agents = [];
let connections = [];

async function loadFlow() {
  try {
    const d = await apiGet('/api/agents');
    agents = d.agents || [];
    connections = d.connections || [];
    renderNodes();
    setTimeout(drawEdges, 80);
    const real = agents.filter(a => !a.virtual).length;
    document.getElementById('statusText').textContent = `${real} agente${real !== 1 ? 's' : ''} ativos`;
    document.getElementById('statusDot').style.background = real > 0 ? 'var(--green)' : 'var(--red)';
  } catch (e) {
    document.getElementById('statusText').textContent = 'Erro ao conectar';
    document.getElementById('statusDot').style.background = 'var(--red)';
  }
}

function renderNodes() {
  const layer = document.getElementById('nodesLayer');
  layer.textContent = '';
  // Divider between agents and projects
  const hasExtras = agents.some(a => a.category);
  if (hasExtras) {
    const divider = document.createElement('div');
    divider.className = 'canvas-divider';
    divider.style.top = '575px';
    const lbl = document.createElement('div');
    lbl.className = 'canvas-divider-label';
    lbl.textContent = 'Projetos & Ferramentas';
    divider.appendChild(lbl);
    layer.appendChild(divider);
  }
  agents.forEach(a => {
    const div = document.createElement('div');
    div.className = 'node' + (a.virtual ? ' virtual' : '');
    div.id = 'node-' + a.id;
    div.style.left = a.x + 'px';
    div.style.top = a.y + 'px';
    div.onclick = () => (a.virtual !== true) && openAgent(a);
    // Category label
    if (a.category) {
      const cat = document.createElement('div');
      cat.className = 'node-cat';
      cat.style.color = a.color;
      cat.textContent = a.category === 'juridico' ? 'Juridico' : a.category === 'financas' ? 'Financas' : a.category === 'ai' ? 'IA' : a.category === 'analytics' ? 'Analytics' : a.category;
      div.appendChild(cat);
    }
    // Header
    const header = document.createElement('div');
    header.className = 'node-header';
    header.style.background = a.color + '22';
    header.style.borderBottom = '1px solid ' + a.color + '33';
    const icon = document.createElement('span');
    icon.className = 'node-icon';
    icon.textContent = a.icon;
    const name = document.createElement('span');
    name.className = 'node-name';
    name.textContent = a.name;
    header.appendChild(icon);
    header.appendChild(name);
    div.appendChild(header);
    // Body
    const body = document.createElement('div');
    body.className = 'node-body';
    if (a.virtual) {
      const vd = document.createElement('div');
      vd.className = 'node-desc';
      vd.style.color = a.color;
      vd.textContent = a.name;
      body.appendChild(vd);
    } else {
      const desc = document.createElement('div');
      desc.className = 'node-desc';
      desc.textContent = a.description || '';
      body.appendChild(desc);
      if (a.stack) {
        const st = document.createElement('span');
        st.className = 'node-stack';
        st.textContent = a.stack;
        body.appendChild(st);
      }
      const badges = document.createElement('div');
      badges.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px';
      if (a.schedule) {
        const sb = document.createElement('span');
        sb.className = 'node-badge';
        sb.textContent = a.schedule;
        badges.appendChild(sb);
      }
      if (a.has_report) {
        const rb = document.createElement('span');
        rb.className = 'node-badge ok';
        rb.textContent = '\u2713 ' + (a.report_date || 'relat\u00f3rio');
        badges.appendChild(rb);
      } else {
        const rb = document.createElement('span');
        rb.className = 'node-badge warn';
        rb.textContent = 'sem relat\u00f3rio';
        badges.appendChild(rb);
      }
      body.appendChild(badges);
    }
    div.appendChild(body);
    // Port
    const port = document.createElement('div');
    port.className = 'node-port-out';
    port.style.borderColor = a.color + '66';
    div.appendChild(port);
    layer.appendChild(div);
  });
}

function drawEdges() {
  const svg = document.getElementById('edgesSvg');
  const canvas = document.getElementById('canvasInner');
  const cr = canvas.getBoundingClientRect();
  svg.innerHTML = '';
  connections.forEach(c => {
    const fn = document.getElementById('node-' + c.from);
    const tn = document.getElementById('node-' + c.to);
    if (!fn || !tn) return;
    const fr = fn.getBoundingClientRect();
    const tr = tn.getBoundingClientRect();
    const x1 = fr.right - cr.left + 4;
    const y1 = fr.top + fr.height / 2 - cr.top;
    const x2 = tr.left - cr.left - 4;
    const y2 = tr.top + tr.height / 2 - cr.top;
    const cp = Math.abs(x2 - x1) * 0.55;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', `M${x1},${y1} C${x1 + cp},${y1} ${x2 - cp},${y2} ${x2},${y2}`);
    const fromA = agents.find(a => a.id === c.from);
    path.setAttribute('stroke', fromA?.color || '#6b7280');
    path.setAttribute('class', 'edge-path');
    svg.appendChild(path);
    // Label
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 - 8;
    const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    txt.setAttribute('x', mx);
    txt.setAttribute('y', my);
    txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('class', 'edge-label');
    txt.textContent = c.label || '';
    svg.appendChild(txt);
    // Arrow
    const arr = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    const ang = Math.atan2(y2 - y1, x2 - x1);
    const ax = x2, ay = y2, len = 7;
    const p1x = ax - len * Math.cos(ang - 0.4), p1y = ay - len * Math.sin(ang - 0.4);
    const p2x = ax - len * Math.cos(ang + 0.4), p2y = ay - len * Math.sin(ang + 0.4);
    arr.setAttribute('points', `${ax},${ay} ${p1x},${p1y} ${p2x},${p2y}`);
    arr.setAttribute('fill', fromA?.color || '#6b7280');
    arr.setAttribute('opacity', '0.6');
    svg.appendChild(arr);
  });
}

window.addEventListener('resize', () => setTimeout(drawEdges, 100));
