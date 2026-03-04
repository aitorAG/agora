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

function moneyCompact(value) {
  const amount = Number(value || 0);
  if (amount >= 1) return `$${amount.toFixed(2)}`;
  if (amount >= 0.01) return `$${amount.toFixed(4)}`;
  return `$${amount.toFixed(6)}`;
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

function parseIsoDay(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
  if (!match) return null;
  const parsed = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function buildDayRange(days) {
  const uniqueDays = [...new Set(
    (days || [])
      .map((item) => String(item || '').trim())
      .filter(Boolean)
  )].sort((left, right) => left.localeCompare(right));
  if (!uniqueDays.length) return [];
  const start = parseIsoDay(uniqueDays[0]);
  const end = parseIsoDay(uniqueDays[uniqueDays.length - 1]);
  if (!start || !end) return uniqueDays;
  const output = [];
  const cursor = new Date(start.getTime());
  while (cursor.getTime() <= end.getTime()) {
    output.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return output;
}

function shortDayLabel(day) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(day || ''));
  if (!match) return String(day || '');
  return `${match[3]}/${match[2]}`;
}

function pickTickIndices(length, maxTicks = 4) {
  if (length <= 0) return [];
  if (length <= maxTicks) return Array.from({ length }, (_, index) => index);
  const indices = new Set([0, length - 1]);
  const step = (length - 1) / (maxTicks - 1);
  for (let index = 1; index < maxTicks - 1; index += 1) {
    indices.add(Math.round(step * index));
  }
  return [...indices].sort((left, right) => left - right);
}

function buildLinePath(points) {
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');
}

function renderTimeSeriesChart(targetId, seriesItems, options = {}) {
  const node = document.getElementById(targetId);
  if (!node) return;
  const preparedSeries = (seriesItems || [])
    .filter((item) => item && Array.isArray(item.values));
  if (!preparedSeries.length) {
    setEmpty(node);
    return;
  }

  const days = buildDayRange(
    preparedSeries.flatMap((item) => item.values.map((point) => point.day))
  );
  if (!days.length) {
    setEmpty(node);
    return;
  }

  const rows = days.map((day) => ({
    day,
    values: preparedSeries.map(() => 0),
  }));
  const rowsByDay = new Map(rows.map((row) => [row.day, row]));
  preparedSeries.forEach((series, seriesIndex) => {
    series.values.forEach((point) => {
      const row = rowsByDay.get(String(point.day || ''));
      if (row) {
        row.values[seriesIndex] = Number(point.value || 0);
      }
    });
  });

  const width = 640;
  const height = 260;
  const padding = { top: 18, right: 18, bottom: 34, left: 64 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(...rows.flatMap((row) => row.values), 1);
  const valueFormatter = options.valueFormatter || integer;
  const axisValueFormatter = options.axisValueFormatter || valueFormatter;
  const latestValueFormatter = options.latestValueFormatter || valueFormatter;
  const xStep = rows.length === 1 ? 0 : plotWidth / (rows.length - 1);
  const pointX = (index) => (rows.length === 1
    ? padding.left + (plotWidth / 2)
    : padding.left + (xStep * index));

  const chartSeries = preparedSeries.map((series, seriesIndex) => {
    const points = rows.map((row, rowIndex) => ({
      x: pointX(rowIndex),
      y: padding.top + plotHeight - ((row.values[seriesIndex] / maxValue) * plotHeight),
      value: row.values[seriesIndex],
    }));
    return {
      ...series,
      seriesIndex,
      points,
      path: buildLinePath(points),
    };
  });

  const yTicks = Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3;
    const value = maxValue * (1 - ratio);
    return {
      label: axisValueFormatter(value),
      y: padding.top + (plotHeight * ratio),
    };
  });
  const xTickIndices = pickTickIndices(rows.length, 4);
  const latestRow = rows[rows.length - 1];

  node.innerHTML = `
    <div class="time-series">
      <div class="time-series-legend">
        ${chartSeries.map((series) => `
          <div class="legend-item">
            <span class="legend-swatch" style="--series:${series.color}"></span>
            <span>${series.label}</span>
          </div>
        `).join('')}
      </div>
      <svg class="time-series-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        ${yTicks.map((tick) => `
          <line x1="${padding.left}" y1="${tick.y}" x2="${width - padding.right}" y2="${tick.y}" class="time-series-grid-line"></line>
          <text x="${padding.left - 8}" y="${tick.y + 4}" text-anchor="end" class="time-series-grid-label">${tick.label}</text>
        `).join('')}
        ${xTickIndices.map((index) => `
          <text x="${pointX(index)}" y="${height - 8}" text-anchor="middle" class="time-series-grid-label">${shortDayLabel(rows[index].day)}</text>
        `).join('')}
        ${chartSeries.map((series) => `
          <path d="${series.path}" class="time-series-line" style="--series:${series.color}"></path>
          ${series.points.map((point) => `
            <circle cx="${point.x}" cy="${point.y}" r="3.5" class="time-series-point" style="--series:${series.color}"></circle>
          `).join('')}
        `).join('')}
      </svg>
      <div class="time-series-summary">
        <div class="summary-day">Ultimo punto: ${latestRow.day}</div>
        ${chartSeries.map((series) => `
          <div class="summary-item">
            <span class="legend-swatch" style="--series:${series.color}"></span>
            <span>${series.label}: ${latestValueFormatter(latestRow.values[series.seriesIndex])}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `;
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

  renderTimeSeriesChart('usersChart', [
    { label: 'Registros', color: 'var(--accent)', values: data.series.registered_users_per_day || [] },
    { label: 'Accesos', color: 'var(--accent-2)', values: data.series.user_accesses_per_day || [] },
  ]);
  renderTimeSeriesChart('gamesChart', [
    { label: 'Partidas activas', color: 'var(--warn)', values: data.series.games_played_per_day || [] },
  ]);
  renderTimeSeriesChart('costChart', [
    { label: 'Entrada', color: 'var(--accent)', values: data.series.cost_input_per_day || [] },
    { label: 'Salida', color: 'var(--accent-2)', values: data.series.cost_output_per_day || [] },
    { label: 'Total', color: 'var(--warn)', values: data.series.cost_total_per_day || [] },
  ], {
    valueFormatter: moneyCompact,
    axisValueFormatter: moneyCompact,
    latestValueFormatter: moneyCompact,
  });
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
