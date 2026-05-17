/* ── State ────────────────────────────────────────────────────────────────── */
const state = {
  currentView: 'dashboard',
  status: null,
  repos: [],
  reposTotal: 0,
  reposPage: 1,
  reposPerPage: 50,
  reposSort: 'stars',
  reposFilter: { category: '', language: '', search: '', archived: null },
  categories: [],
  languages: new Set(),
  insights: null,
  config: null,
  lists: [],
  listRepos: {},           // listId -> repos array
  listReposOpen: {},       // listId -> bool
  listEditing: {},         // listId -> bool
  searchQuery: '',
  searchTopK: 10,
  searchResults: null,
  charts: {},
};

/* ── API Client ───────────────────────────────────────────────────────────── */
const api = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
  async post(path, data) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
  async put(path, data) {
    const r = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
  async del(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${r.status}`);
    }
    return r.json();
  },
};

/* ── SSE Helper ───────────────────────────────────────────────────────────── */
function runSSE(path, title, onDone) {
  showProgress(title);
  const logEl = document.getElementById('progress-log');

  fetch(path, { method: 'POST' }).then(resp => {
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function pump() {
      reader.read().then(({ done, value }) => {
        if (done) {
          hideProgress();
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(part.slice(6));
            if (event.type === 'progress') {
              appendLog(logEl, event.message);
            } else if (event.type === 'done') {
              appendLog(logEl, 'Done!');
              hideProgress();
              if (onDone) onDone(event.result);
            } else if (event.type === 'error') {
              appendLog(logEl, 'Error: ' + event.message);
              hideProgress();
              toast('Error', event.message, 'error');
            }
          } catch (_) {}
        }
        pump();
      });
    }
    pump();
  }).catch(err => {
    hideProgress();
    toast('Error', err.message, 'error');
  });
}

function appendLog(el, message) {
  const line = document.createElement('span');
  line.className = 'progress-log-line';
  line.textContent = message;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

/* ── Progress Overlay ─────────────────────────────────────────────────────── */
function showProgress(title) {
  document.getElementById('progress-title').textContent = title;
  document.getElementById('progress-log').innerHTML = '';
  document.getElementById('progress-overlay').classList.remove('hidden');
}

function hideProgress() {
  document.getElementById('progress-overlay').classList.add('hidden');
}

/* ── Toast ────────────────────────────────────────────────────────────────── */
const TOAST_ICONS = {
  success: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`,
  error: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
  info: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  warning: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
};

function toast(title, message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `
    ${TOAST_ICONS[type] || TOAST_ICONS.info}
    <div class="toast-body">
      <div class="toast-title">${escHtml(title)}</div>
      ${message ? `<div class="toast-message">${escHtml(message)}</div>` : ''}
    </div>
  `;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('removing');
    setTimeout(() => el.remove(), 220);
  }, duration);
}

/* ── Utilities ────────────────────────────────────────────────────────────── */
function escHtml(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatStars(n) {
  if (n == null) return '0';
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
  return String(n);
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const diff = Math.floor((now - d) / 86400000);
  if (diff === 0) return 'today';
  if (diff === 1) return 'yesterday';
  if (diff < 30) return `${diff}d ago`;
  if (diff < 365) return `${Math.floor(diff / 30)}mo ago`;
  return `${Math.floor(diff / 365)}y ago`;
}

function langClass(lang) {
  if (!lang) return '';
  const map = {
    'Python': 'lang-python', 'TypeScript': 'lang-typescript',
    'JavaScript': 'lang-javascript', 'Rust': 'lang-rust',
    'Go': 'lang-go', 'Java': 'lang-java', 'Ruby': 'lang-ruby',
    'C': 'lang-c', 'C++': 'lang-cpp', 'Shell': 'lang-shell',
  };
  return map[lang] || '';
}

function categoryColor(name) {
  if (!name) return 'hsl(220,40%,55%)';
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash << 5) - hash + name.charCodeAt(i);
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue}, 60%, 65%)`;
}

function categoryBadgeStyle(name) {
  if (!name) return '';
  const color = categoryColor(name);
  return `style="color:${color};background:${color}22;border:1px solid ${color}33"`;
}

function renderLangBadge(lang) {
  if (!lang) return '';
  const cls = langClass(lang);
  return `<span class="badge badge-lang ${cls}">${escHtml(lang)}</span>`;
}

function renderCategoryBadge(cat) {
  if (!cat) return '<span class="text-muted" style="font-size:11px">—</span>';
  return `<span class="badge badge-category" ${categoryBadgeStyle(cat)} title="${escHtml(cat)}">${escHtml(cat)}</span>`;
}

function renderStars(n) {
  return `<span class="stars"><svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>${formatStars(n)}</span>`;
}

function skeletonRows(n, cols) {
  let html = '';
  for (let i = 0; i < n; i++) {
    html += '<tr>';
    for (let j = 0; j < cols; j++) html += `<td><span class="skeleton skeleton-text" style="width:${60 + Math.random() * 30}%"></span></td>`;
    html += '</tr>';
  }
  return html;
}

/* ── Router ───────────────────────────────────────────────────────────────── */
function navigateTo(viewName) {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.dataset.view === viewName);
  });
  document.querySelectorAll('.view').forEach(el => {
    el.classList.toggle('active', el.id === `view-${viewName}`);
  });
  state.currentView = viewName;
  renderView(viewName);
}

function renderView(name) {
  switch (name) {
    case 'dashboard': renderDashboard(); break;
    case 'repos': renderRepos(); break;
    case 'search': renderSearch(); break;
    case 'insights': renderInsights(); break;
    case 'lists': renderLists(); break;
    case 'settings': renderSettings(); break;
  }
}

/* ── Dashboard ────────────────────────────────────────────────────────────── */
async function renderDashboard() {
  const el = document.getElementById('view-dashboard');
  el.innerHTML = `
    <div class="view-header">
      <div>
        <h1 class="view-title">Dashboard</h1>
        <p class="view-subtitle">Overview of your starred repositories</p>
      </div>
    </div>
    <div class="stats-grid" id="dash-stats">
      ${[...Array(4)].map(() => `<div class="stat-card"><span class="skeleton skeleton-stat"></span><span class="skeleton skeleton-text short"></span></div>`).join('')}
    </div>
    <div class="dashboard-actions">
      <div class="action-card" id="action-sync">
        <div class="action-icon sync">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.47"/></svg>
        </div>
        <div class="action-info">
          <div class="action-title">Sync Stars</div>
          <div class="action-desc">Fetch latest starred repos</div>
        </div>
      </div>
      <div class="action-card" id="action-classify">
        <div class="action-icon classify">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 7H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
        </div>
        <div class="action-info">
          <div class="action-title">Classify</div>
          <div class="action-desc">Categorize with AI</div>
        </div>
      </div>
      <div class="action-card" id="action-organize">
        <div class="action-icon organize">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
        </div>
        <div class="action-info">
          <div class="action-title">Organize</div>
          <div class="action-desc">Push to GitHub Lists</div>
        </div>
      </div>
    </div>
    <div class="charts-row" id="dash-charts">
      <div class="chart-wrap">
        <div class="chart-title">Category Distribution</div>
        <div class="chart-container"><canvas id="chart-categories"></canvas></div>
      </div>
      <div class="chart-wrap">
        <div class="chart-title">Top Languages</div>
        <div class="chart-container"><canvas id="chart-languages"></canvas></div>
      </div>
    </div>
    <div class="table-wrap">
      <div class="table-header">
        <span class="table-title">Recent Repositories</span>
        <button class="btn btn-ghost btn-sm" onclick="navigateTo('repos')">View All →</button>
      </div>
      <table>
        <thead><tr>
          <th>Repository</th><th>Language</th><th>Category</th><th>Stars</th><th>Updated</th>
        </tr></thead>
        <tbody id="dash-recent-tbody">
          ${skeletonRows(8, 5)}
        </tbody>
      </table>
    </div>
  `;

  // Bind action cards
  document.getElementById('action-sync').addEventListener('click', () => {
    runSSE('/api/sync', 'Syncing starred repositories...', () => {
      toast('Sync complete', 'Repositories updated successfully', 'success');
      refreshStatus();
      if (state.currentView === 'dashboard') renderDashboard();
    });
  });
  document.getElementById('action-classify').addEventListener('click', () => {
    runSSE('/api/classify', 'Classifying repositories with AI...', () => {
      toast('Classification complete', 'Categories updated', 'success');
      if (state.currentView === 'dashboard') renderDashboard();
    });
  });
  document.getElementById('action-organize').addEventListener('click', () => {
    runSSE('/api/organize', 'Organizing into GitHub Lists...', (result) => {
      const msg = result && result.message ? result.message : 'Lists organized';
      toast('Organize complete', msg, 'success');
    });
  });

  // Load data
  try {
    const [statusData, catData, repoData] = await Promise.all([
      api.get('/api/status'),
      api.get('/api/categories'),
      api.get('/api/repos?per_page=10&sort=updated'),
    ]);
    state.status = statusData;

    renderDashStats(statusData);
    renderDashRecent(repoData.repos, catData);
    renderDashCharts(catData, statusData);
  } catch (err) {
    toast('Failed to load dashboard', err.message, 'error');
  }
}

function renderDashStats(s) {
  const lastSync = s.last_sync ? formatDate(s.last_sync) : 'Never';
  document.getElementById('dash-stats').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Total Stars</div>
      <div class="stat-value">${formatStars(s.total_repos)}</div>
      <div class="stat-meta">repositories starred</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Classified</div>
      <div class="stat-value">${s.classified_count}</div>
      <div class="stat-meta">of ${s.total_repos} categorized</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Categories</div>
      <div class="stat-value">${s.categories_count}</div>
      <div class="stat-meta">configured categories</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Last Sync</div>
      <div class="stat-value" style="font-size:18px">${lastSync}</div>
      <div class="stat-meta">${s.last_sync ? new Date(s.last_sync).toLocaleDateString() : 'Not synced yet'}</div>
    </div>
  `;
}

function renderDashRecent(repos, catData) {
  const tbody = document.getElementById('dash-recent-tbody');
  if (!repos || repos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">
      <div class="empty-state-title">No repositories yet</div>
      <div class="empty-state-desc">Run Sync to fetch your starred repositories.</div>
    </div></td></tr>`;
    return;
  }
  tbody.innerHTML = repos.map(r => `
    <tr>
      <td class="td-primary"><a href="${escHtml(r.url)}" target="_blank" rel="noopener">${escHtml(r.full_name)}</a>
        ${r.archived ? '<span class="badge badge-archived" style="margin-left:4px">archived</span>' : ''}
      </td>
      <td>${renderLangBadge(r.language)}</td>
      <td>${renderCategoryBadge(r.category)}</td>
      <td>${renderStars(r.stars)}</td>
      <td class="td-muted">${formatDate(r.updated_at)}</td>
    </tr>
  `).join('');
}

function renderDashCharts(catData, statusData) {
  // destroy existing
  Object.values(state.charts).forEach(c => c.destroy());
  state.charts = {};

  const catCtx = document.getElementById('chart-categories');
  if (catCtx && catData && catData.categories) {
    const cats = catData.categories.filter(c => c.count > 0);
    if (cats.length > 0) {
      state.charts.cat = new Chart(catCtx, {
        type: 'doughnut',
        data: {
          labels: cats.map(c => c.name),
          datasets: [{
            data: cats.map(c => c.count),
            backgroundColor: cats.map(c => categoryColor(c.name) + '99'),
            borderColor: cats.map(c => categoryColor(c.name)),
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.parsed}`,
              },
            },
          },
        },
      });
    } else {
      catCtx.parentElement.innerHTML = '<div class="empty-state"><div class="empty-state-title">No classifications yet</div></div>';
    }
  }

  const langCtx = document.getElementById('chart-languages');
  if (langCtx && statusData && statusData.top_languages) {
    const langs = statusData.top_languages;
    if (langs.length > 0) {
      state.charts.lang = new Chart(langCtx, {
        type: 'bar',
        data: {
          labels: langs.map(l => l.name),
          datasets: [{
            data: langs.map(l => l.count),
            backgroundColor: '#1f6feb99',
            borderColor: '#58a6ff',
            borderWidth: 1,
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: 'y',
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { color: '#21262d' },
              ticks: { color: '#8b949e' },
            },
            y: {
              grid: { display: false },
              ticks: { color: '#8b949e' },
            },
          },
        },
      });
    }
  }
}

/* ── Repositories ─────────────────────────────────────────────────────────── */
async function renderRepos() {
  const el = document.getElementById('view-repos');

  // Build filter options if we have them
  const catOptions = state.categories.length
    ? state.categories.map(c => `<option value="${escHtml(c.name)}" ${state.reposFilter.category === c.name ? 'selected' : ''}>${escHtml(c.name)}</option>`).join('')
    : '';

  const langOptions = [...state.languages].sort().map(l =>
    `<option value="${escHtml(l)}" ${state.reposFilter.language === l ? 'selected' : ''}>${escHtml(l)}</option>`
  ).join('');

  el.innerHTML = `
    <div class="view-header">
      <div>
        <h1 class="view-title">Repositories</h1>
        <p class="view-subtitle" id="repos-count-label">Loading...</p>
      </div>
    </div>
    <div class="filter-bar">
      <div class="filter-search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input id="repos-search" type="text" class="form-input" placeholder="Search repos..." value="${escHtml(state.reposFilter.search)}" />
      </div>
      <select id="repos-cat" class="form-select">
        <option value="">All Categories</option>
        ${catOptions}
      </select>
      <select id="repos-lang" class="form-select">
        <option value="">All Languages</option>
        ${langOptions}
      </select>
      <select id="repos-archived" class="form-select" style="min-width:120px">
        <option value="">Any</option>
        <option value="false" ${state.reposFilter.archived === false ? 'selected' : ''}>Active</option>
        <option value="true" ${state.reposFilter.archived === true ? 'selected' : ''}>Archived</option>
      </select>
      <div class="filter-divider"></div>
      <select id="repos-sort" class="form-select" style="min-width:110px">
        <option value="stars" ${state.reposSort === 'stars' ? 'selected' : ''}>Stars</option>
        <option value="name" ${state.reposSort === 'name' ? 'selected' : ''}>Name</option>
        <option value="updated" ${state.reposSort === 'updated' ? 'selected' : ''}>Updated</option>
      </select>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Repository</th>
          <th>Description</th>
          <th>Language</th>
          <th>Category</th>
          <th>Stars</th>
          <th>Updated</th>
        </tr></thead>
        <tbody id="repos-tbody">${skeletonRows(12, 6)}</tbody>
      </table>
    </div>
    <div class="pagination" id="repos-pagination"></div>
  `;

  // Wire filters
  let searchTimeout;
  document.getElementById('repos-search').addEventListener('input', e => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      state.reposFilter.search = e.target.value;
      state.reposPage = 1;
      loadRepos();
    }, 300);
  });

  document.getElementById('repos-cat').addEventListener('change', e => {
    state.reposFilter.category = e.target.value;
    state.reposPage = 1;
    loadRepos();
  });

  document.getElementById('repos-lang').addEventListener('change', e => {
    state.reposFilter.language = e.target.value;
    state.reposPage = 1;
    loadRepos();
  });

  document.getElementById('repos-archived').addEventListener('change', e => {
    const v = e.target.value;
    state.reposFilter.archived = v === '' ? null : (v === 'true');
    state.reposPage = 1;
    loadRepos();
  });

  document.getElementById('repos-sort').addEventListener('change', e => {
    state.reposSort = e.target.value;
    state.reposPage = 1;
    loadRepos();
  });

  await loadRepos();
}

async function loadRepos() {
  const params = new URLSearchParams({
    page: state.reposPage,
    per_page: state.reposPerPage,
    sort: state.reposSort,
  });
  if (state.reposFilter.category) params.set('category', state.reposFilter.category);
  if (state.reposFilter.language) params.set('language', state.reposFilter.language);
  if (state.reposFilter.search) params.set('search', state.reposFilter.search);
  if (state.reposFilter.archived !== null) params.set('archived', state.reposFilter.archived);

  const tbody = document.getElementById('repos-tbody');
  if (tbody) tbody.innerHTML = skeletonRows(10, 6);

  try {
    const data = await api.get(`/api/repos?${params}`);
    state.repos = data.repos;
    state.reposTotal = data.total;

    // Populate language set from first load
    data.repos.forEach(r => { if (r.language) state.languages.add(r.language); });

    const label = document.getElementById('repos-count-label');
    if (label) label.textContent = `${data.total} repositories`;

    const tbody2 = document.getElementById('repos-tbody');
    if (!tbody2) return;

    if (data.repos.length === 0) {
      tbody2.innerHTML = `<tr><td colspan="6"><div class="empty-state">
        <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3h18v18H3zM3 9h18M9 21V9"/></svg>
        <div class="empty-state-title">No repositories found</div>
        <div class="empty-state-desc">Try adjusting your filters or run Sync to fetch your stars.</div>
      </div></td></tr>`;
    } else {
      tbody2.innerHTML = data.repos.map(r => `
        <tr>
          <td>
            <a href="${escHtml(r.url)}" target="_blank" rel="noopener" class="td-primary">${escHtml(r.full_name)}</a>
            ${r.archived ? '<span class="badge badge-archived" style="margin-left:4px">archived</span>' : ''}
            ${r.is_fork ? '<span class="badge badge-fork" style="margin-left:4px">fork</span>' : ''}
          </td>
          <td class="td-description" title="${escHtml(r.description)}">${escHtml(r.description) || '<span class="text-muted">—</span>'}</td>
          <td>${renderLangBadge(r.language)}</td>
          <td>${renderCategoryBadge(r.category)}</td>
          <td>${renderStars(r.stars)}</td>
          <td class="td-muted">${formatDate(r.updated_at)}</td>
        </tr>
      `).join('');
    }

    renderPagination();
  } catch (err) {
    toast('Failed to load repos', err.message, 'error');
  }
}

function renderPagination() {
  const el = document.getElementById('repos-pagination');
  if (!el) return;
  const totalPages = Math.ceil(state.reposTotal / state.reposPerPage);
  if (totalPages <= 1) { el.innerHTML = ''; return; }

  const page = state.reposPage;
  let pages = [];

  // Always show first, last, current ± 2
  const shown = new Set();
  [1, totalPages, page - 2, page - 1, page, page + 1, page + 2].forEach(p => {
    if (p >= 1 && p <= totalPages) shown.add(p);
  });

  const sorted = [...shown].sort((a, b) => a - b);
  let prev = 0;
  for (const p of sorted) {
    if (prev > 0 && p - prev > 1) pages.push('…');
    pages.push(p);
    prev = p;
  }

  const start = (page - 1) * state.reposPerPage + 1;
  const end = Math.min(page * state.reposPerPage, state.reposTotal);

  el.innerHTML = `
    <span class="pagination-info">${start}–${end} of ${state.reposTotal}</span>
    <button class="page-btn" ${page === 1 ? 'disabled' : ''} onclick="goPage(${page - 1})">‹</button>
    ${pages.map(p => p === '…' ? `<span class="text-muted" style="padding:0 4px">…</span>` :
      `<button class="page-btn ${p === page ? 'active' : ''}" onclick="goPage(${p})">${p}</button>`
    ).join('')}
    <button class="page-btn" ${page === totalPages ? 'disabled' : ''} onclick="goPage(${page + 1})">›</button>
  `;
}

function goPage(p) {
  state.reposPage = p;
  loadRepos();
  document.querySelector('.content').scrollTop = 0;
}

/* ── Search ───────────────────────────────────────────────────────────────── */
function renderSearch() {
  const el = document.getElementById('view-search');
  el.innerHTML = `
    <div class="view-header">
      <div>
        <h1 class="view-title">Semantic Search</h1>
        <p class="view-subtitle">Find repositories using natural language</p>
      </div>
    </div>
    <div class="search-hero">
      <div class="search-box">
        <input id="search-input" type="text" class="form-input" placeholder="e.g. fast vector database for production..." value="${escHtml(state.searchQuery)}" />
        <button class="btn btn-primary" id="search-btn">Search</button>
      </div>
      <div class="search-controls">
        <div class="slider-wrap">
          <label for="search-topk">Results:</label>
          <input type="range" id="search-topk" min="5" max="30" step="5" value="${state.searchTopK}" />
          <span id="search-topk-val">${state.searchTopK}</span>
        </div>
      </div>
    </div>
    <div id="search-results">
      ${state.searchResults === null ? `
        <div class="empty-state">
          <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <div class="empty-state-title">Search your stars</div>
          <div class="empty-state-desc">Type a description of what you're looking for and find related repositories using semantic similarity.</div>
        </div>
      ` : renderSearchResults(state.searchResults)}
    </div>
  `;

  const input = document.getElementById('search-input');
  const btn = document.getElementById('search-btn');
  const topkInput = document.getElementById('search-topk');
  const topkVal = document.getElementById('search-topk-val');

  topkInput.addEventListener('input', () => {
    state.searchTopK = parseInt(topkInput.value);
    topkVal.textContent = state.searchTopK;
  });

  async function doSearch() {
    const q = input.value.trim();
    if (!q) return;
    state.searchQuery = q;
    btn.disabled = true;
    btn.textContent = 'Searching...';
    const resultsEl = document.getElementById('search-results');
    resultsEl.innerHTML = `<div class="search-results-grid">${[...Array(6)].map(() => `
      <div class="result-card">
        <span class="skeleton skeleton-text medium"></span>
        <span class="skeleton skeleton-text"></span>
        <span class="skeleton skeleton-text short"></span>
      </div>
    `).join('')}</div>`;
    try {
      const data = await api.post('/api/search', { query: q, top_k: state.searchTopK });
      state.searchResults = data.results;
      resultsEl.innerHTML = renderSearchResults(data.results);
    } catch (err) {
      toast('Search failed', err.message, 'error');
      resultsEl.innerHTML = `<div class="empty-state"><div class="empty-state-title">Search failed</div><div class="empty-state-desc">${escHtml(err.message)}</div></div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Search';
    }
  }

  btn.addEventListener('click', doSearch);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
}

function renderSearchResults(results) {
  if (!results || results.length === 0) {
    return `<div class="empty-state">
      <div class="empty-state-title">No results found</div>
      <div class="empty-state-desc">Try different search terms, or sync and embed your repositories first.</div>
    </div>`;
  }
  return `
    <p class="text-secondary mb-16" style="font-size:13px">${results.length} results</p>
    <div class="search-results-grid">
      ${results.map(r => `
        <div class="result-card">
          <div class="result-card-header">
            <a class="result-name" href="${escHtml(r.url)}" target="_blank" rel="noopener">${escHtml(r.full_name)}</a>
            <span class="result-score">score: ${r.score.toFixed(3)}</span>
          </div>
          <div class="score-bar-wrap"><div class="score-bar" style="width:${Math.round(r.score * 100)}%"></div></div>
          <p class="result-desc">${escHtml(r.description) || '<em>No description</em>'}</p>
          <div class="result-footer">
            ${renderLangBadge(r.language)}
            ${renderCategoryBadge(r.category)}
            ${renderStars(r.stars)}
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

/* ── Insights ─────────────────────────────────────────────────────────────── */
async function renderInsights() {
  const el = document.getElementById('view-insights');
  el.innerHTML = `
    <div class="view-header">
      <div>
        <h1 class="view-title">Insights</h1>
        <p class="view-subtitle">Analysis of your starred repositories</p>
      </div>
    </div>
    <div class="insights-stats-row">
      <div class="insight-stat archived" id="insight-archived" onclick="toggleSection('section-archived')">
        <div class="insight-stat-value" id="val-archived"><span class="skeleton skeleton-stat" style="width:60px;margin:auto"></span></div>
        <div class="insight-stat-label">Archived</div>
      </div>
      <div class="insight-stat inactive" id="insight-inactive" onclick="toggleSection('section-inactive')">
        <div class="insight-stat-value" id="val-inactive"><span class="skeleton skeleton-stat" style="width:60px;margin:auto"></span></div>
        <div class="insight-stat-label">Inactive (&gt;18mo)</div>
      </div>
      <div class="insight-stat duplicates" id="insight-duplicates" onclick="toggleSection('section-duplicates')">
        <div class="insight-stat-value" id="val-duplicates"><span class="skeleton skeleton-stat" style="width:60px;margin:auto"></span></div>
        <div class="insight-stat-label">Potential Duplicates</div>
      </div>
    </div>
    <div class="charts-row" style="margin-bottom:28px">
      <div class="chart-wrap">
        <div class="chart-title">Category Distribution</div>
        <div class="chart-container"><canvas id="insights-chart-cat"></canvas></div>
      </div>
      <div class="chart-wrap">
        <div class="chart-title">Technology Mix</div>
        <div class="chart-container"><canvas id="insights-chart-tech"></canvas></div>
      </div>
    </div>
    <div id="insights-sections"></div>
  `;

  try {
    const data = await api.get('/api/insights');
    if (data.error) {
      el.querySelector('#insights-sections').innerHTML = `<div class="empty-state">
        <div class="empty-state-title">${escHtml(data.error)}</div>
      </div>`;
      return;
    }
    state.insights = data;

    document.getElementById('val-archived').textContent = data.archived_count;
    document.getElementById('val-inactive').textContent = data.inactive_count;
    document.getElementById('val-duplicates').textContent = data.duplicate_count;

    renderInsightCharts(data);
    renderInsightSections(data);
  } catch (err) {
    toast('Failed to load insights', err.message, 'error');
  }
}

function renderInsightCharts(data) {
  // Category chart
  const catCtx = document.getElementById('insights-chart-cat');
  if (catCtx && data.category_distribution.length > 0) {
    const cats = data.category_distribution.slice(0, 15);
    if (state.charts.insightsCat) state.charts.insightsCat.destroy();
    state.charts.insightsCat = new Chart(catCtx, {
      type: 'bar',
      data: {
        labels: cats.map(c => c.name),
        datasets: [{
          data: cats.map(c => c.count),
          backgroundColor: cats.map(c => categoryColor(c.name) + '99'),
          borderColor: cats.map(c => categoryColor(c.name)),
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#21262d' }, ticks: { color: '#8b949e' } },
          y: { grid: { display: false }, ticks: { color: '#8b949e', font: { size: 11 } } },
        },
      },
    });
  }

  // Tech chart
  const techCtx = document.getElementById('insights-chart-tech');
  if (techCtx && data.tech_distribution.length > 0) {
    const techs = data.tech_distribution.slice(0, 12);
    if (state.charts.insightsTech) state.charts.insightsTech.destroy();
    state.charts.insightsTech = new Chart(techCtx, {
      type: 'doughnut',
      data: {
        labels: techs.map(t => t.name),
        datasets: [{
          data: techs.map(t => t.count),
          backgroundColor: techs.map((_, i) => `hsl(${i * 30}, 60%, 55%)99`),
          borderColor: techs.map((_, i) => `hsl(${i * 30}, 60%, 55%)`),
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: '#8b949e', font: { size: 11 }, boxWidth: 12, padding: 8 },
          },
        },
      },
    });
  }
}

function renderInsightSections(data) {
  const el = document.getElementById('insights-sections');
  el.innerHTML = `
    ${renderCollapsible('section-archived', `Archived Repositories`, data.archived_count,
      data.archived_repos.length === 0 ? '<p class="text-muted">None found.</p>' : `
        <table class="list-repos-table"><thead><tr><th>Repository</th><th>Link</th></tr></thead>
        <tbody>${data.archived_repos.map(r => `<tr>
          <td>${escHtml(r.full_name)}</td>
          <td><a href="${escHtml(r.url)}" target="_blank" rel="noopener">GitHub ↗</a></td>
        </tr>`).join('')}</tbody></table>
      `)}

    ${renderCollapsible('section-inactive', `Inactive Repositories (>18 months)`, data.inactive_count,
      data.inactive_repos.length === 0 ? '<p class="text-muted">None found.</p>' : `
        <table class="list-repos-table"><thead><tr><th>Repository</th><th>Last Update</th><th>Link</th></tr></thead>
        <tbody>${data.inactive_repos.map(r => `<tr>
          <td>${escHtml(r.full_name)}</td>
          <td class="text-muted">${formatDate(r.updated_at)}</td>
          <td><a href="${escHtml(r.url)}" target="_blank" rel="noopener">GitHub ↗</a></td>
        </tr>`).join('')}</tbody></table>
      `)}

    ${renderCollapsible('section-duplicates', `Potential Duplicate Groups`, data.duplicate_count,
      data.duplicate_groups.length === 0 ? '<p class="text-muted">None found.</p>' : `
        ${data.duplicate_groups.map((group, i) => `
          <div style="margin-bottom:12px;padding:10px;background:var(--bg-subtle);border-radius:6px">
            <div class="text-secondary mb-8" style="font-size:11px">Group ${i + 1}</div>
            ${group.map(r => `<div style="margin-bottom:4px"><a href="${escHtml(r.url)}" target="_blank" rel="noopener">${escHtml(r.full_name)}</a></div>`).join('')}
          </div>
        `).join('')}
      `)}
  `;
}

function renderCollapsible(id, title, count, bodyHtml) {
  return `
    <div class="collapsible-section">
      <div class="collapsible-header" id="hdr-${id}" onclick="toggleSection('${id}')">
        <div class="collapsible-title">
          ${title}
          <span class="collapsible-count">${count}</span>
        </div>
        <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
      <div class="collapsible-body" id="${id}">
        ${bodyHtml}
      </div>
    </div>
  `;
}

function toggleSection(id) {
  const body = document.getElementById(id);
  const hdr = document.getElementById(`hdr-${id}`);
  if (!body) return;
  const isOpen = body.classList.toggle('open');
  hdr && hdr.classList.toggle('open', isOpen);
}

/* ── Lists ────────────────────────────────────────────────────────────────── */
async function renderLists() {
  const el = document.getElementById('view-lists');
  el.innerHTML = `
    <div class="view-header">
      <div>
        <h1 class="view-title">GitHub Lists</h1>
        <p class="view-subtitle">Manage your starred repository lists</p>
      </div>
      <div class="view-actions">
        <div class="new-list-form">
          <input type="text" id="new-list-name" class="form-input" placeholder="New list name..." />
          <button class="btn btn-primary" id="btn-create-list">Create</button>
        </div>
      </div>
    </div>
    <div id="lists-grid" class="lists-grid">
      ${[...Array(4)].map(() => `<div class="list-card"><div class="list-card-header"><span class="skeleton skeleton-text medium"></span></div></div>`).join('')}
    </div>
  `;

  document.getElementById('btn-create-list').addEventListener('click', createList);
  document.getElementById('new-list-name').addEventListener('keydown', e => {
    if (e.key === 'Enter') createList();
  });

  await loadLists();
}

async function loadLists() {
  try {
    const data = await api.get('/api/lists');
    state.lists = data.lists;
    renderListsGrid();
  } catch (err) {
    const grid = document.getElementById('lists-grid');
    if (grid) grid.innerHTML = `<div class="empty-state">
      <div class="empty-state-title">Failed to load lists</div>
      <div class="empty-state-desc">${escHtml(err.message)}</div>
    </div>`;
  }
}

function renderListsGrid() {
  const grid = document.getElementById('lists-grid');
  if (!grid) return;
  if (state.lists.length === 0) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/></svg>
      <div class="empty-state-title">No lists yet</div>
      <div class="empty-state-desc">Create a list above, or run Organize to auto-generate lists from categories.</div>
    </div>`;
    return;
  }
  grid.innerHTML = state.lists.map(list => renderListCard(list)).join('');
}

function renderListCard(list) {
  const isEditing = state.listEditing[list.id];
  const isOpen = state.listReposOpen[list.id];

  return `
    <div class="list-card" id="card-${list.id}">
      <div class="list-card-header">
        <div class="list-name">
          <svg style="width:16px;height:16px;color:var(--warning-fg);flex-shrink:0" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
          ${isEditing
            ? `<input class="list-name-input" id="edit-name-${list.id}" value="${escHtml(list.name)}" />`
            : `<span>${escHtml(list.name)}</span>`
          }
        </div>
        <div class="list-actions">
          ${isEditing ? `
            <button class="btn btn-sm btn-success" onclick="saveListName('${list.id}')">Save</button>
            <button class="btn btn-sm btn-ghost" onclick="cancelEdit('${list.id}')">Cancel</button>
          ` : `
            <button class="btn btn-icon btn-ghost" title="Rename" onclick="startEdit('${list.id}')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="btn btn-icon btn-ghost" title="Delete" onclick="deleteList('${list.id}', '${escHtml(list.name)}')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
            </button>
          `}
        </div>
      </div>
      <div class="list-card-footer">
        <button class="toggle-repos-btn" onclick="toggleListRepos('${list.id}')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px"><polyline points="${isOpen ? '18 15 12 9 6 15' : '6 9 12 15 18 9'}"/></svg>
          ${isOpen ? 'Hide' : 'View'} repositories
        </button>
      </div>
      <div class="list-repos-section ${isOpen ? 'open' : ''}" id="repos-section-${list.id}">
        ${renderListReposSection(list.id)}
      </div>
    </div>
  `;
}

function renderListReposSection(listId) {
  const repos = state.listRepos[listId];
  if (repos === undefined) {
    return `<div class="list-repos-loading">Loading...</div>`;
  }
  if (repos === null) {
    return `<div class="list-repos-loading text-danger">Failed to load</div>`;
  }
  if (repos.length === 0) {
    return `<div class="list-repos-loading text-muted">No repositories in this list</div>`;
  }
  return `
    <table class="list-repos-table">
      <thead><tr><th>Repository</th><th>Language</th><th>Stars</th><th>Link</th></tr></thead>
      <tbody>
        ${repos.map(r => `<tr>
          <td class="td-primary">${escHtml(r.full_name)}</td>
          <td>${renderLangBadge(r.language)}</td>
          <td>${renderStars(r.stars)}</td>
          <td><a href="${escHtml(r.url)}" target="_blank" rel="noopener">↗</a></td>
        </tr>`).join('')}
      </tbody>
    </table>
  `;
}

function startEdit(listId) {
  state.listEditing[listId] = true;
  rerenderCard(listId);
  const input = document.getElementById(`edit-name-${listId}`);
  if (input) { input.focus(); input.select(); }
}

function cancelEdit(listId) {
  state.listEditing[listId] = false;
  rerenderCard(listId);
}

async function saveListName(listId) {
  const input = document.getElementById(`edit-name-${listId}`);
  if (!input) return;
  const newName = input.value.trim();
  if (!newName) { toast('Error', 'Name cannot be empty', 'error'); return; }

  const list = state.lists.find(l => l.id === listId);
  if (!list) return;

  try {
    await api.put(`/api/lists/${listId}`, { name: newName });
    list.name = newName;
    state.listEditing[listId] = false;
    rerenderCard(listId);
    toast('Renamed', `List renamed to "${newName}"`, 'success');
  } catch (err) {
    toast('Failed to rename', err.message, 'error');
  }
}

async function deleteList(listId, name) {
  if (!confirm(`Delete list "${name}"? This cannot be undone.`)) return;
  try {
    await api.del(`/api/lists/${listId}`);
    state.lists = state.lists.filter(l => l.id !== listId);
    delete state.listRepos[listId];
    delete state.listReposOpen[listId];
    delete state.listEditing[listId];
    renderListsGrid();
    toast('Deleted', `List "${name}" deleted`, 'success');
  } catch (err) {
    toast('Failed to delete', err.message, 'error');
  }
}

async function toggleListRepos(listId) {
  const isNowOpen = !state.listReposOpen[listId];
  state.listReposOpen[listId] = isNowOpen;

  const section = document.getElementById(`repos-section-${listId}`);
  if (!section) return;

  if (isNowOpen) {
    section.classList.add('open');
    if (state.listRepos[listId] === undefined) {
      section.innerHTML = `<div class="list-repos-loading">Loading...</div>`;
      try {
        const data = await api.get(`/api/lists/${listId}/repos`);
        state.listRepos[listId] = data.repos;
      } catch (err) {
        state.listRepos[listId] = null;
      }
      section.innerHTML = renderListReposSection(listId);
    }
  } else {
    section.classList.remove('open');
  }

  // Update toggle button text
  rerenderCard(listId);
}

function rerenderCard(listId) {
  const card = document.getElementById(`card-${listId}`);
  if (!card) return;
  const list = state.lists.find(l => l.id === listId);
  if (!list) return;
  card.outerHTML = renderListCard(list);
}

async function createList() {
  const input = document.getElementById('new-list-name');
  if (!input) return;
  const name = input.value.trim();
  if (!name) { toast('Error', 'Name cannot be empty', 'error'); return; }

  try {
    const data = await api.post('/api/lists', { name });
    state.lists.push({ id: data.id, name: data.name });
    input.value = '';
    renderListsGrid();
    toast('Created', `List "${data.name}" created`, 'success');
  } catch (err) {
    toast('Failed to create list', err.message, 'error');
  }
}

/* ── Settings ─────────────────────────────────────────────────────────────── */
async function renderSettings() {
  const el = document.getElementById('view-settings');
  el.innerHTML = `
    <div class="view-header">
      <div>
        <h1 class="view-title">Settings</h1>
        <p class="view-subtitle">Configure the application</p>
      </div>
    </div>
    <div class="settings-layout">
      <div class="card" id="settings-form-wrap">
        <div class="card-body">
          <div class="skeleton skeleton-text"></div>
          <div class="skeleton skeleton-text medium"></div>
          <div class="skeleton skeleton-text short"></div>
        </div>
      </div>
    </div>
  `;

  try {
    const cfg = await api.get('/api/config');
    state.config = cfg;
    renderSettingsForm(cfg);
  } catch (err) {
    toast('Failed to load config', err.message, 'error');
  }
}

function renderSettingsForm(cfg) {
  const wrap = document.getElementById('settings-form-wrap');
  if (!wrap) return;

  const catTagsHtml = (cfg.categories || []).map(cat =>
    `<span class="category-tag">
      ${escHtml(cat)}
      <button class="category-tag-remove" onclick="removeCategory('${escHtml(cat)}')" title="Remove">×</button>
    </span>`
  ).join('');

  wrap.innerHTML = `
    <div class="card-body">
      <form id="settings-form">
        <div class="form-section">
          <div class="form-section-title">LLM Settings</div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label" for="cfg-model">Model</label>
              <input type="text" id="cfg-model" class="form-input" value="${escHtml(cfg.model)}" placeholder="gpt-4.1-mini" />
            </div>
            <div class="form-group">
              <label class="form-label" for="cfg-api-base">API Base URL</label>
              <input type="text" id="cfg-api-base" class="form-input" value="${escHtml(cfg.api_base_url)}" placeholder="https://api.openai.com/v1" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label" for="cfg-api-key">API Key Env Var</label>
              <input type="text" id="cfg-api-key" class="form-input" value="${escHtml(cfg.api_key_env)}" placeholder="OPENAI_API_KEY" />
              <p class="form-hint">Name of the environment variable containing your API key</p>
            </div>
            <div class="form-group">
              <label class="form-label" for="cfg-embed">Embedding Model</label>
              <input type="text" id="cfg-embed" class="form-input" value="${escHtml(cfg.embedding_model)}" placeholder="text-embedding-3-small" />
            </div>
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">Rate Limits</div>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label" for="cfg-llm-rpm">LLM Requests / Minute</label>
              <input type="number" id="cfg-llm-rpm" class="form-input" value="${cfg.llm_requests_per_minute}" min="1" max="600" />
            </div>
            <div class="form-group">
              <label class="form-label" for="cfg-gh-rpm">GitHub Requests / Minute</label>
              <input type="number" id="cfg-gh-rpm" class="form-input" value="${cfg.github_requests_per_minute}" min="1" max="600" />
            </div>
          </div>
          <div class="form-group" style="max-width:200px">
            <label class="form-label" for="cfg-inactive">Inactive Months Threshold</label>
            <input type="number" id="cfg-inactive" class="form-input" value="${cfg.inactive_months}" min="1" max="60" />
          </div>
        </div>

        <div class="form-section">
          <div class="form-section-title">Categories</div>
          <p class="form-hint mb-16">Categories used for LLM classification. Add or remove as needed.</p>
          <div class="categories-editor" id="cat-editor">${catTagsHtml}</div>
          <div class="category-add-row">
            <input type="text" id="new-cat-input" class="form-input" placeholder="Add category..." />
            <button type="button" class="btn btn-secondary" onclick="addCategory()">Add</button>
          </div>
        </div>

        <div class="divider"></div>
        <div style="display:flex;gap:10px">
          <button type="submit" class="btn btn-primary" id="save-cfg-btn">Save Configuration</button>
          <button type="button" class="btn btn-ghost" onclick="renderSettings()">Reset</button>
        </div>
      </form>
    </div>
  `;

  document.getElementById('new-cat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); addCategory(); }
  });

  document.getElementById('settings-form').addEventListener('submit', async e => {
    e.preventDefault();
    await saveConfig();
  });
}

function addCategory() {
  const input = document.getElementById('new-cat-input');
  if (!input) return;
  const val = input.value.trim();
  if (!val) return;
  if (!state.config.categories) state.config.categories = [];
  if (state.config.categories.includes(val)) {
    toast('Duplicate', 'Category already exists', 'warning');
    return;
  }
  state.config.categories.push(val);
  input.value = '';
  refreshCatEditor();
}

function removeCategory(cat) {
  if (!state.config) return;
  state.config.categories = state.config.categories.filter(c => c !== cat);
  refreshCatEditor();
}

function refreshCatEditor() {
  const editor = document.getElementById('cat-editor');
  if (!editor || !state.config) return;
  editor.innerHTML = (state.config.categories || []).map(cat =>
    `<span class="category-tag">
      ${escHtml(cat)}
      <button class="category-tag-remove" onclick="removeCategory('${escHtml(cat)}')" title="Remove">×</button>
    </span>`
  ).join('');
}

async function saveConfig() {
  const btn = document.getElementById('save-cfg-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }

  const payload = {
    model: document.getElementById('cfg-model')?.value.trim() || undefined,
    embedding_model: document.getElementById('cfg-embed')?.value.trim() || undefined,
    api_base_url: document.getElementById('cfg-api-base')?.value.trim() || undefined,
    api_key_env: document.getElementById('cfg-api-key')?.value.trim() || undefined,
    categories: state.config?.categories,
    inactive_months: parseInt(document.getElementById('cfg-inactive')?.value) || undefined,
    llm_requests_per_minute: parseInt(document.getElementById('cfg-llm-rpm')?.value) || undefined,
    github_requests_per_minute: parseInt(document.getElementById('cfg-gh-rpm')?.value) || undefined,
  };

  // Remove undefined
  Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

  try {
    await api.post('/api/config', payload);
    toast('Saved', 'Configuration saved successfully', 'success');
    const cfg = await api.get('/api/config');
    state.config = cfg;
  } catch (err) {
    toast('Failed to save', err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Save Configuration'; }
  }
}

/* ── Status Refresh ───────────────────────────────────────────────────────── */
async function refreshStatus() {
  try {
    state.status = await api.get('/api/status');
  } catch (_) {}
}

async function loadCategories() {
  try {
    const data = await api.get('/api/categories');
    state.categories = data.categories;
  } catch (_) {}
}

/* ── Init ─────────────────────────────────────────────────────────────────── */
function init() {
  // Navigation
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      navigateTo(el.dataset.view);
    });
  });

  // Keyboard shortcut: / to focus search
  document.addEventListener('keydown', e => {
    if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
      const activeEl = document.activeElement;
      if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) return;
      e.preventDefault();
      navigateTo('search');
      setTimeout(() => {
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.focus();
      }, 50);
    }
  });

  // Load initial data
  loadCategories();
  refreshStatus();

  // Render initial view
  renderView('dashboard');
}

// Wait for DOM
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
