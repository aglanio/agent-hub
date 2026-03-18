/**
 * Side panel — tabs, chat, report, skill.
 */
let currentAgent = null;

// ── PANEL ──────────────────────────────────────────────
function openAgent(a) {
  currentAgent = a.id;
  document.querySelectorAll('.node').forEach(n => n.classList.remove('selected'));
  const nd = document.getElementById('node-' + a.id);
  if (nd) nd.classList.add('selected');
  const panel = document.getElementById('sidePanel');
  panel.classList.add('open');
  document.getElementById('panelIcon').textContent = a.icon;
  document.getElementById('panelIcon').style.background = a.color + '22';
  document.getElementById('panelTitle').textContent = a.name;
  document.getElementById('panelSub').textContent = a.schedule ? '\u23f0 ' + a.schedule : '';
  switchTab('chat', document.querySelector('.ptab'));
  loadChat(a.id);
  setTimeout(drawEdges, 350);
}

function closePanel() {
  document.getElementById('sidePanel').classList.remove('open');
  document.querySelectorAll('.node').forEach(n => n.classList.remove('selected'));
  currentAgent = null;
  setTimeout(drawEdges, 350);
}

function switchTab(tab, btn) {
  document.querySelectorAll('.ptab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.add('active');
  if (!currentAgent) return;
  if (tab === 'report') loadReport(currentAgent);
  if (tab === 'skill') loadSkill(currentAgent);
}

// ── CHAT ───────────────────────────────────────────────
async function loadChat(aid) {
  const box = document.getElementById('chatMessages');
  box.innerHTML = '<div class="msg system">Carregando hist\u00f3rico...</div>';
  try {
    const d = await apiGet('/api/chat/' + aid + '/history');
    box.innerHTML = '';
    if (!d.length) {
      const a = agents.find(x => x.id === aid);
      const welcome = document.createElement('div');
      welcome.className = 'msg system';
      welcome.textContent = `Ol\u00e1! Converse com o agente ${a?.name || aid}. Posso responder perguntas sobre meu funcionamento, relat\u00f3rios e configura\u00e7\u00f5es.`;
      box.appendChild(welcome);
    } else {
      d.forEach(m => addMsg(m.role, m.content, false));
    }
  } catch (e) {
    box.innerHTML = '<div class="msg system">Erro ao carregar hist\u00f3rico</div>';
  }
}

function addMsg(role, text, scroll = true) {
  const box = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  box.appendChild(div);
  if (scroll) box.scrollTop = box.scrollHeight;
}

async function sendChat() {
  const inp = document.getElementById('chatInput');
  const btn = document.getElementById('sendBtn');
  const text = inp.value.trim();
  if (!text || !currentAgent) return;
  inp.value = '';
  inp.style.height = '38px';
  addMsg('user', text);
  btn.disabled = true;
  const typing = document.createElement('div');
  typing.className = 'msg assistant';
  typing.id = 'typing';
  typing.innerHTML = '<span style="opacity:.5">digitando...</span>';
  document.getElementById('chatMessages').appendChild(typing);
  document.getElementById('chatMessages').scrollTop = 99999;
  try {
    const d = await apiPost('/api/chat', { agent_id: currentAgent, message: text });
    document.getElementById('typing')?.remove();
    addMsg('assistant', d.reply || '...');
  } catch (e) {
    document.getElementById('typing')?.remove();
    addMsg('assistant', 'Erro de conex\u00e3o');
  }
  btn.disabled = false;
  inp.focus();
}

// ── REPORT ─────────────────────────────────────────────
async function loadReport(aid) {
  const tab = document.getElementById('tabReport');
  tab.innerHTML = '<div class="report-empty">Carregando relat\u00f3rio...</div>';
  try {
    const d = await apiGet('/api/agents/' + aid + '/report');
    if (d.error) {
      tab.innerHTML = `<div class="report-empty">${esc(d.error)}</div>`;
      return;
    }
    const cards = [];
    if (d.resumo_executivo) cards.push(reportCard('Resumo Executivo', d.resumo_executivo));
    if (d.realizacoes_do_dia?.length) cards.push(reportListCard('Realizacoes', d.realizacoes_do_dia));
    if (d.prioridades_amanha?.length) cards.push(reportListCard('Prioridades Amanha', d.prioridades_amanha));
    if (d.pontos_atencao?.length) cards.push(reportListCard('Atencao', d.pontos_atencao));
    if (d.novidades_tecnicas?.length) cards.push(reportListCard('Novidades Tecnicas', d.novidades_tecnicas));
    if (d.features_prioritarias?.length) cards.push(reportListCard('Features', d.features_prioritarias));
    if (d.recomendacoes_tecnicas?.length) cards.push(reportListCard('Recomendacoes', d.recomendacoes_tecnicas));
    if (d.status_sistemas) cards.push(reportStatusCard(d.status_sistemas));
    const meta = `<div style="font-size:.7rem;color:var(--text3);margin-bottom:8px">${esc(d.data || '')} ${esc(d.hora || '')}</div>`;
    tab.innerHTML = meta + (cards.length ? cards.join('') : `<pre style="font-size:.75rem;color:var(--text2);white-space:pre-wrap">${JSON.stringify(d, null, 2)}</pre>`);
  } catch (e) {
    tab.innerHTML = '<div class="report-empty">Erro ao carregar</div>';
  }
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s || '');
  return d.innerHTML;
}

function reportCard(title, val) {
  return `<div class="report-card"><div class="report-title">${esc(title)}</div><div class="report-value">${esc(val)}</div></div>`;
}

function reportListCard(title, arr) {
  return `<div class="report-card"><div class="report-title">${esc(title)}</div><ul class="report-list">${arr.map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>`;
}

function reportStatusCard(st) {
  const items = Object.entries(st).map(([k, v]) =>
    `<div style="display:flex;justify-content:space-between;font-size:.8rem;padding:4px 0;border-bottom:1px solid var(--border)"><span style="color:var(--text2)">${esc(k)}</span><span style="color:${v === 'ok' ? 'var(--green)' : v === 'warning' ? 'var(--amber)' : 'var(--red)'}">${esc(v)}</span></div>`
  ).join('');
  return `<div class="report-card"><div class="report-title">Status Sistemas</div>${items}</div>`;
}

// ── SKILL ──────────────────────────────────────────────
async function loadSkill(aid) {
  const pre = document.getElementById('skillPre');
  pre.textContent = 'Carregando...';
  try {
    const d = await apiGet('/api/agents/' + aid + '/skill');
    pre.textContent = d.content || 'Skill nao encontrada';
  } catch (e) {
    pre.textContent = 'Erro ao carregar';
  }
}
