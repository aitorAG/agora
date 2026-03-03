const PROXIED_BASE = window.location.pathname.startsWith('/admin/observability')
  ? '/admin/observability'
  : '';
const API_BASE = PROXIED_BASE ? `${PROXIED_BASE}/api` : '';

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

async function getJSON(path, params = {}) {
  const url = new URL(apiUrl(path), window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      url.searchParams.set(key, String(value));
    }
  });
  const response = await fetch(url.toString(), { credentials: 'include' });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function money(value) {
  return `$${Number(value || 0).toFixed(6)}`;
}

function integer(value) {
  return Intl.NumberFormat('es-ES').format(Math.round(Number(value || 0)));
}

function ms(value) {
  return `${integer(value)} ms`;
}

function formatDate(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
}

function setEmpty(node, message = 'Sin datos') {
  if (!node) return;
  node.innerHTML = `<div class="empty">${message}</div>`;
}

function renderCards(targetId, items) {
  const node = document.getElementById(targetId);
  if (!node) return;
  if (!items.length) {
    node.innerHTML = '';
    return;
  }
  node.innerHTML = items.map((item) => `
    <article class="card">
      <div class="label">${item.label}</div>
      <div class="value">${item.value}</div>
      ${item.hint ? `<div class="hint">${item.hint}</div>` : ''}
    </article>
  `).join('');
}

function renderTable(tableId, rows, columns, emptyMessage = 'Sin datos') {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!tbody) return;
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${columns.length}"><div class="empty">${emptyMessage}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((row) => `<tr>${columns.map((col) => `<td>${col(row)}</td>`).join('')}</tr>`).join('');
}

function renderSingleChart(targetId, series) {
  const node = document.getElementById(targetId);
  if (!node) return;
  if (!series.length) {
    setEmpty(node);
    return;
  }
  const max = Math.max(...series.map((item) => Number(item.value || 0)), 1);
  node.innerHTML = series.map((item) => {
    const width = Math.max(4, Math.round((Number(item.value || 0) / max) * 100));
    return `
      <div class="chart-row">
        <div class="day">${item.day}</div>
        <div class="bar-single"><div class="bar-fill" style="width:${width}%"></div></div>
        <div class="value-pill">${integer(item.value)}</div>
      </div>
    `;
  }).join('');
}

function renderDualChart(targetId, seriesA, seriesB, labelA, labelB) {
  const node = document.getElementById(targetId);
  if (!node) return;
  const map = new Map();
  [...seriesA, ...seriesB].forEach((item) => {
    if (!map.has(item.day)) map.set(item.day, { day: item.day, a: 0, b: 0 });
  });
  seriesA.forEach((item) => map.get(item.day).a = Number(item.value || 0));
  seriesB.forEach((item) => map.get(item.day).b = Number(item.value || 0));
  const rows = [...map.values()].sort((left, right) => String(left.day).localeCompare(String(right.day)));
  if (!rows.length) {
    setEmpty(node);
    return;
  }
  const max = Math.max(...rows.map((row) => Math.max(row.a, row.b)), 1);
  node.innerHTML = rows.map((row) => {
    const widthA = Math.max(4, Math.round((row.a / max) * 100));
    const widthB = Math.max(4, Math.round((row.b / max) * 100));
    return `
      <div class="chart-row">
        <div class="day">${row.day}</div>
        <div class="bar-stack">
          <div class="bar-a" style="width:${widthA}%"></div>
          <div class="bar-b" style="width:${widthB}%"></div>
        </div>
        <div class="value-pill">${labelA}: ${integer(row.a)} · ${labelB}: ${integer(row.b)}</div>
      </div>
    `;
  }).join('');
}

function renderSelect(selectId, items, valueKey, labelKey, placeholder) {
  const select = document.getElementById(selectId);
  if (!select) return;
  const options = [`<option value="">${placeholder}</option>`].concat(
    items.map((item) => `<option value="${item[valueKey]}">${item[labelKey]}</option>`)
  );
  const current = select.value;
  select.innerHTML = options.join('');
  if (current && items.some((item) => String(item[valueKey]) === current)) {
    select.value = current;
  }
}

function renderRangeMetric(minValue, avgValue, maxValue, formatter) {
  const safeMin = Number(minValue || 0);
  const safeAvg = Number(avgValue || 0);
  const safeMax = Math.max(Number(maxValue || 0), 1);
  const minWidth = Math.max(4, Math.round((safeMin / safeMax) * 100));
  const avgWidth = Math.max(4, Math.round((safeAvg / safeMax) * 100));
  const maxWidth = 100;
  return `
    <div class="metric-range">
      <div class="range-bars">
        <div class="range-bar range-min" style="width:${minWidth}%"></div>
        <div class="range-bar range-avg" style="width:${avgWidth}%"></div>
        <div class="range-bar range-max" style="width:${maxWidth}%"></div>
      </div>
      <div class="range-meta">min ${formatter(safeMin)} · avg ${formatter(safeAvg)} · max ${formatter(safeMax)}</div>
    </div>
  `;
}

function renderMessages(items) {
  const node = document.getElementById('messageLog');
  if (!node) return;
  if (!items.length) {
    setEmpty(node, 'Sin mensajes persistidos');
    return;
  }
  node.innerHTML = items.map((item) => `
    <article class="message-item">
      <div class="message-meta">${item.sender} (${formatDate(item.timestamp)})</div>
      <div>${item.content}</div>
    </article>
  `).join('');
}

async function loadUsers() {
  const payload = await getJSON('/v1/options/users');
  const items = payload.items || [];
  const userItems = [
    { user_id: '__all__', label: 'Todos los usuarios' },
    ...items,
  ];
  renderSelect('userSelect', userItems, 'user_id', 'label', 'Selecciona un usuario');
  renderSelect('gameUserSelect', items, 'user_id', 'label', 'Selecciona un usuario');
  const userSelect = document.getElementById('userSelect');
  if (userSelect && !userSelect.value) {
    userSelect.value = '__all__';
  }
  return items;
}

async function loadGamesForUser(selectId, userId) {
  const payload = await getJSON('/v1/options/games', userId ? { user_id: userId } : {});
  renderSelect(selectId, payload.items || [], 'game_id', 'label', 'Selecciona una partida');
  return payload.items || [];
}

async function loadGeneral() {
  const data = await getJSON('/v1/analytics/general');
  renderCards('generalActivityKpis', [
    { label: 'Usuarios registrados', value: integer(data.kpis.total_users) },
    { label: 'Partidas activas hoy', value: integer(data.kpis.active_games_today), hint: 'Con al menos un mensaje hoy' },
  ]);
  renderCards('generalCostKpis', [
    { label: 'Tokens medios por partida', value: integer(data.kpis.avg_tokens_per_game) },
    { label: 'Tokens maximos por partida', value: integer(data.kpis.max_tokens_per_game) },
    { label: 'Tokens totales trackeados', value: integer(data.kpis.total_tracked_tokens) },
    { label: 'Coste medio por partida', value: money(data.kpis.avg_cost_per_game) },
    { label: 'Coste maximo por partida', value: money(data.kpis.max_cost_per_game) },
    { label: 'Coste historico total', value: money(data.kpis.historical_total_cost) },
  ]);
  renderCards('generalLatencyKpis', [
    { label: 'Tiempo medio de espera', value: ms(data.kpis.avg_wait_ms), hint: 'Suma de latencias LLM por interaccion' },
  ]);

  renderDualChart(
    'usersChart',
    data.series.registered_users_per_day || [],
    data.series.user_accesses_per_day || [],
    'Reg',
    'Acc'
  );
  renderSingleChart('gamesChart', data.series.games_played_per_day || []);
  renderSingleChart('tokensChart', data.series.tokens_per_day || []);
  renderTable('usersCostTable', data.rankings?.users_by_cost || [], [
    (row) => row.username,
    (row) => money(row.total_cost),
    (row) => integer(row.total_tokens),
    (row) => integer(row.tracked_games),
  ], 'Sin gasto trackeado todavia');
}

async function loadAgents() {
  const data = await getJSON('/v1/analytics/agents');
  renderTable('agentsTable', data.items || [], [
    (row) => row.agent_label,
    (row) => integer(row.calls),
    (row) => money(row.cost_total),
    (row) => renderRangeMetric(row.min_tokens_per_call, row.avg_tokens_per_call, row.max_tokens_per_call, integer),
    (row) => renderRangeMetric(row.min_duration_ms, row.avg_duration_ms, row.max_duration_ms, ms),
  ]);
}

async function loadUserDetail() {
  const userId = document.getElementById('userSelect')?.value || '';
  const params = userId && userId !== '__all__' ? { user_id: userId } : {};
  const data = await getJSON('/v1/analytics/user-detail', params);
  const summaryHint = data.user.id === '__all__'
    ? `${integer(data.user.user_count || 0)} usuarios en total`
    : `Creado: ${formatDate(data.user.created_at)}`;
  renderCards('userKpis', [
    { label: 'Usuario', value: data.user.username, hint: summaryHint },
    { label: 'Partidas historicas', value: integer(data.user.game_count) },
    { label: 'Tokens in/out/total', value: `${integer(data.tokens.input)} / ${integer(data.tokens.output)} / ${integer(data.tokens.total)}` },
    { label: 'Coste in/out/total', value: `${money(data.cost.input)} / ${money(data.cost.output)} / ${money(data.cost.total)}` },
  ]);
  renderTable('userGamesTable', data.games || [], [
    (row) => row.display_name,
    (row) => integer(row.turns),
    (row) => row.status,
    (row) => formatDate(row.last_player_message_at),
  ]);
}

async function loadGameDetail() {
  const gameId = document.getElementById('gameSelect')?.value || '';
  if (!gameId) {
    renderCards('gameKpis', []);
    renderTable('gameAgentsTable', [], [() => '', () => '', () => '', () => '', () => ''], 'Selecciona una partida');
    renderMessages([]);
    return;
  }
  const data = await getJSON('/v1/analytics/game-detail', { game_id: gameId });
  renderCards('gameKpis', [
    { label: 'Partida', value: data.game.display_name },
    { label: 'Usuario', value: data.game.username, hint: `Creada: ${formatDate(data.game.created_at)}` },
    { label: 'Turnos', value: integer(data.game.turns), hint: `Estado: ${data.game.status}` },
    { label: 'Tokens in/out/total', value: `${integer(data.tokens.input)} / ${integer(data.tokens.output)} / ${integer(data.tokens.total)}` },
    { label: 'Coste in/out/total', value: `${money(data.cost.input)} / ${money(data.cost.output)} / ${money(data.cost.total)}` },
  ]);
  renderTable('gameAgentsTable', data.agents || [], [
    (row) => row.agent_name,
    (row) => row.agent_type,
    (row) => `${integer(row.input_tokens)} / ${integer(row.output_tokens)} / ${integer(row.total_tokens)}`,
    (row) => money(row.cost_total),
    (row) => ms(row.avg_duration_ms),
  ], 'Sin llamadas LLM trackeadas para esta partida');
  renderMessages(data.messages || []);
}

function bindTabs() {
  document.querySelectorAll('.tab').forEach((button) => {
    button.addEventListener('click', () => {
      const target = button.dataset.tab;
      document.querySelectorAll('.tab').forEach((item) => item.classList.toggle('is-active', item === button));
      document.querySelectorAll('.tab-panel').forEach((panel) => {
        panel.classList.toggle('is-active', panel.dataset.panel === target);
      });
    });
  });
}

async function refreshAll() {
  await loadUsers();
  await loadGamesForUser('gameSelect', document.getElementById('gameUserSelect')?.value || '');
  await Promise.all([loadGeneral(), loadAgents(), loadUserDetail(), loadGameDetail()]);
}

bindTabs();
document.getElementById('refreshAll')?.addEventListener('click', refreshAll);
document.getElementById('loadUser')?.addEventListener('click', loadUserDetail);
document.getElementById('loadGame')?.addEventListener('click', loadGameDetail);
document.getElementById('userSelect')?.addEventListener('change', loadUserDetail);
document.getElementById('gameUserSelect')?.addEventListener('change', async (event) => {
  const userId = event.target.value || '';
  await loadGamesForUser('gameSelect', userId);
  await loadGameDetail();
});
document.getElementById('gameSelect')?.addEventListener('change', loadGameDetail);

refreshAll().catch((error) => {
  console.error(error);
  document.querySelectorAll('.chart, .cards, tbody, #messageLog').forEach((node) => {
    if (node && !node.innerHTML) {
      node.innerHTML = '<div class="empty">No se pudieron cargar las metricas</div>';
    }
  });
});
