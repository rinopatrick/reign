const API = '';
let activeProfile = localStorage.getItem('reign_profile') || 'default';

function profileHeaders(extra = {}) {
  return activeProfile === 'default' ? extra : { ...extra, 'X-Reign-Profile': activeProfile };
}

async function apiGet(path) {
  const r = await fetch(API + path, { headers: profileHeaders() });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(API + path, {
    method: 'POST',
    headers: profileHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function apiDelete(path) {
  const r = await fetch(API + path, { method: 'DELETE', headers: profileHeaders() });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function apiFetch(path, init = {}) {
  const headers = profileHeaders(init.headers || {});
  return fetch(API + path, { ...init, headers });
}

function formatMoney(value, currency = 'IDR') {
  const n = Number(value);
  if (currency === 'IDR') return 'Rp ' + Math.abs(n).toLocaleString('id-ID');
  return currency + ' ' + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2 });
}

function formatDate(d) {
  return new Date(d).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatMonthYear(d) {
  return new Date(d).toLocaleDateString('id-ID', { month: 'short', year: 'numeric' });
}

function safeColor(c) {
  return /^#[0-9a-fA-F]{6}$/.test(c || '') ? c : '#718096';
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

let charts = [];

function destroyCharts() {
  charts.forEach(c => c.destroy());
  charts = [];
}

// Sidebar
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  const ov = document.getElementById('sidebar-overlay');
  const isOpen = !sb.classList.contains('-translate-x-full');
  if (isOpen) {
    sb.classList.add('-translate-x-full');
    ov.classList.add('hidden');
  } else {
    sb.classList.remove('-translate-x-full');
    ov.classList.remove('hidden');
  }
}

// Dark mode
function toggleDarkMode() {
  const html = document.documentElement;
  const isDark = html.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
  updateDarkModeIcons(isDark);
}

function updateDarkModeIcons(isDark) {
  document.getElementById('moon-icon').classList.toggle('hidden', !isDark);
  document.getElementById('sun-icon').classList.toggle('hidden', isDark);
}

(function initTheme() {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  if (saved === 'dark' || (!saved && prefersDark)) {
    document.documentElement.classList.add('dark');
    updateDarkModeIcons(true);
  }
})();

// Navigation
let currentView = 'dashboard';

function navigate(view) {
  currentView = view;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.remove('bg-slate-800', 'text-white');
    el.classList.add('text-slate-300');
  });
  const active = document.getElementById('nav-' + view);
  if (active) {
    active.classList.add('bg-slate-800', 'text-white');
    active.classList.remove('text-slate-300');
  }
  document.getElementById('page-title').textContent = view.charAt(0).toUpperCase() + view.slice(1);
  destroyCharts();
  // Close mobile sidebar after nav
  if (window.innerWidth < 768) toggleSidebar();
  renderView(view);
}

async function renderView(view) {
  const content = document.getElementById('content');
  content.innerHTML = '<div class="text-gray-400 dark:text-gray-500">Loading...</div>';
  try {
    if (view === 'dashboard') await renderDashboard(content);
    else if (view === 'transactions') await renderTransactions(content);
    else if (view === 'accounts') await renderAccounts(content);
    else if (view === 'budgets') await renderBudgets(content);
    else if (view === 'categories') await renderCategories(content);
    else if (view === 'goals') await renderGoals(content);
    else if (view === 'invest') await renderInvest(content);
    else if (view === 'forecast') await renderForecast(content);
    else if (view === 'calendar') await renderCalendar(content);
    else if (view === 'recurring') await renderRecurring(content);
    else if (view === 'settings') await renderSettings(content);
  } catch (e) {
    content.innerHTML = `<div class="text-red-500">Error: ${escapeHtml(e.message)}</div>`;
  }
}

// ============== DASHBOARD ==============
async function renderDashboard(container) {
  const now = new Date();
  const [summary, categories, trends] = await Promise.all([
    apiGet('/api/dashboard/summary?currency=IDR'),
    apiGet('/api/dashboard/categories?currency=IDR'),
    apiGet('/api/dashboard/trends?currency=IDR'),
  ]);

  // Fetch extra stats
  const txs = await apiGet('/api/transactions?limit=5');
  const recs = await apiGet('/api/recurring');
  const budgets = await apiGet(`/api/budgets?year=${now.getFullYear()}&month=${now.getMonth()+1}`);
  const overBudgets = budgets.filter(b => (Math.abs(Number(b.spent || 0)) / Number(b.amount)) > 0.9);

  const netColor = summary.month_net >= 0 ? 'text-emerald-600' : 'text-rose-600';
  const netSign = summary.month_net >= 0 ? '+' : '';

  container.innerHTML = `
    ${overBudgets.length > 0 ? `
    <div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 mb-6 flex items-start gap-3">
      <svg class="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
      <div>
        <p class="text-sm font-medium text-amber-800 dark:text-amber-300">Budget Alert</p>
        <p class="text-xs text-amber-700 dark:text-amber-400 mt-0.5">${escapeHtml(overBudgets.map(b => b.category?.name + ' (' + Math.round((Math.abs(Number(b.spent||0))/Number(b.amount))*100) + '%)').join(', '))} — over 90% spent.</p>
      </div>
    </div>` : ''}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm">
        <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Income</p>
        <p class="text-2xl font-bold text-emerald-600 mt-1 tabular-nums">${formatMoney(summary.month_income)}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm">
        <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Expense</p>
        <p class="text-2xl font-bold text-rose-600 mt-1 tabular-nums">${formatMoney(summary.month_expense)}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm">
        <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Net</p>
        <p class="text-2xl font-bold ${netColor} mt-1 tabular-nums">${netSign}${formatMoney(summary.month_net)}</p>
      </div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm flex flex-col">
        <h3 class="text-sm font-semibold mb-4 dark:text-gray-200">Monthly Trend</h3>
        <div id="trend-chart-wrapper" class="flex-1 min-h-[220px]">
          <canvas id="trendChart"></canvas>
        </div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm flex flex-col">
        <h3 class="text-sm font-semibold mb-4 dark:text-gray-200">Spending by Category</h3>
        <div id="cat-chart-wrapper" class="flex-1 min-h-[220px] flex items-center justify-center">
          <canvas id="catChart"></canvas>
        </div>
      </div>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm mb-6">
      <h3 class="text-sm font-semibold mb-1 dark:text-gray-200">Arus Kas (Sankey)</h3>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">Pemasukan bulan berjalan ke kategori pengeluaran dan sisa.</p>
      <div id="sankey" class="overflow-x-auto"></div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
      <div class="lg:col-span-2 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm">
        <h3 class="text-sm font-semibold mb-4 dark:text-gray-200">Recent Transactions</h3>
        <div id="recent-tx" class="space-y-2"></div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm">
        <h3 class="text-sm font-semibold mb-4 dark:text-gray-200">Activity Summary</h3>
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500 dark:text-gray-400">Total Transactions</span>
            <span class="text-sm font-semibold dark:text-gray-200">${txs.length}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500 dark:text-gray-400">Reconciled</span>
            <span class="text-sm font-semibold text-emerald-600">${txs.filter(t => t.is_reconciled).length}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm text-gray-500 dark:text-gray-400">Pending</span>
            <span class="text-sm font-semibold text-amber-600">${txs.filter(t => !t.is_reconciled).length}</span>
          </div>
          <div class="border-t dark:border-gray-700 pt-3 mt-3">
            <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">Upcoming Recurring</p>
            ${recs.filter(r => r.active).slice(0, 3).map(r => `
              <div class="flex items-center justify-between py-1">
                <span class="text-xs dark:text-gray-300">${escapeHtml(r.description)}</span>
                <span class="text-xs font-medium ${r.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${formatMoney(r.amount)}</span>
              </div>
            `).join('') || '<p class="text-xs text-gray-400">No active recurring.</p>'}
          </div>
        </div>
      </div>
    </div>
  `;

  // Trend chart
  const isDark = document.documentElement.classList.contains('dark');
  if (trends && trends.length > 0) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    const gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)';
    const textColor = isDark ? '#9ca3af' : '#6b7280';
    charts.push(new Chart(ctx, {
      type: 'line',
      data: {
        labels: trends.map(t => t.label),
        datasets: [
          { label: 'Income', data: trends.map(t => Number(t.income)), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', fill: true, tension: 0.3 },
          { label: 'Expense', data: trends.map(t => Math.abs(Number(t.expense))), borderColor: '#f43f5e', backgroundColor: 'rgba(244,63,94,0.1)', fill: true, tension: 0.3 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: textColor } } },
        scales: {
          x: { grid: { color: gridColor }, ticks: { color: textColor } },
          y: { grid: { color: gridColor }, ticks: { color: textColor } }
        }
      }
    }));
  } else {
    document.getElementById('trend-chart-wrapper').innerHTML = '<p class="text-sm text-gray-400 text-center">Not enough data for trend.</p>';
  }

  // Category chart
  if (categories.length > 0) {
    const ctx = document.getElementById('catChart').getContext('2d');
    charts.push(new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: categories.map(c => c.name),
        datasets: [{
          data: categories.map(c => Math.abs(Number(c.total))),
          backgroundColor: ['#0D1B2A','#1B4965','#0077B6','#90E0EF','#06D6A0','#FFD166','#EF476F','#718096'],
          borderWidth: 0,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'right', labels: { boxWidth: 12, font: { size: 11 }, color: isDark ? '#9ca3af' : '#374151' } } }
      }
    }));
  } else {
    document.getElementById('cat-chart-wrapper').innerHTML = '<p class="text-sm text-gray-400 text-center">No spending yet this month.<br>Add expenses to see the breakdown.</p>';
  }

  await renderSankey();

  const txContainer = document.getElementById('recent-tx');
  if (txs.length === 0) {
    txContainer.innerHTML = '<p class="text-sm text-gray-400">No transactions yet. Import a CSV to get started.</p>';
  } else {
    txContainer.innerHTML = txs.map(tx => `
      <div class="flex items-center justify-between py-2 border-b dark:border-gray-700 last:border-0">
        <div>
          <p class="text-sm font-medium dark:text-gray-200">${escapeHtml(tx.description)}</p>
          <p class="text-xs text-gray-400 dark:text-gray-500">${formatDate(tx.date)} ${tx.category ? '• ' + escapeHtml(tx.category.name) : ''}</p>
        </div>
        <span class="text-sm font-semibold ${tx.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">
          ${tx.amount >= 0 ? '+' : ''}${formatMoney(tx.amount)}
        </span>
      </div>
    `).join('');
  }
}

// ============== TRANSACTIONS ==============
async function renderTransactions(container) {
  const [txs, accounts, categories] = await Promise.all([
    apiGet('/api/transactions?limit=200'),
    apiGet('/api/accounts'),
    apiGet('/api/categories'),
  ]);

  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm overflow-hidden mb-4">
      <div class="p-4 border-b dark:border-gray-700 flex flex-col gap-3">
        <div class="flex flex-col sm:flex-row gap-3 justify-between items-start sm:items-center">
          <h3 class="text-sm font-semibold dark:text-gray-200">Transactions</h3>
          <div class="flex gap-2 flex-wrap">
            <button onclick="openTxModal()" class="text-sm px-3 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 font-medium">+ Add</button>
            <button onclick="openTransferModal()" class="text-sm px-3 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 font-medium">Transfer</button>
            <select id="tx-account-filter" class="text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2" onchange="applyTxFilters()">
              <option value="">All accounts</option>
              ${accounts.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('')}
            </select>
            <select id="tx-category-filter" class="text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2" onchange="applyTxFilters()">
              <option value="">All categories</option>
              ${categories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('')}
            </select>
            <select id="tx-tag-filter" class="text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2" onchange="applyTxFilters()">
              <option value="">All tags</option>
            </select>
            <label class="cursor-pointer inline-flex items-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-500 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>
              Import CSV
              <input type="file" accept=".csv" class="hidden" onchange="importCSV(this)">
            </label>
            <button onclick="exportTransactions('csv')" class="text-sm px-3 py-2 border dark:border-gray-600 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">Export CSV</button>
            <button onclick="exportTransactions('json')" class="text-sm px-3 py-2 border dark:border-gray-600 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">Export JSON</button>
            <label class="cursor-pointer inline-flex items-center gap-2 px-3 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-500 transition">
              Reconcile statement
              <input type="file" accept=".csv,.ofx,.qfx" class="hidden" onchange="reconcileStatement(this)">
            </label>
          </div>
        </div>
        <div class="flex gap-2">
          <input id="tx-search" type="text" placeholder="Search transactions..." class="flex-1 text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2" oninput="applyTxFilters()">
          <input id="tx-start-date" type="date" class="text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2" onchange="applyTxFilters()">
          <input id="tx-end-date" type="date" class="text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2" onchange="applyTxFilters()">
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="bg-gray-50 dark:bg-gray-700 text-xs uppercase text-gray-500 dark:text-gray-400">
            <tr>
              <th class="px-4 py-3"><input type="checkbox" id="tx-select-all" onchange="toggleSelectAll()"></th>
              <th class="px-4 py-3">Date</th>
              <th class="px-4 py-3">Description</th>
              <th class="px-4 py-3">Category</th>
              <th class="px-4 py-3 text-right">Amount</th>
              <th class="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody id="tx-table-body">
            ${txs.length === 0 ? `<tr><td colspan="6" class="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No transactions. Import a CSV to get started.</td></tr>` : ''}
          </tbody>
        </table>
      </div>
      <div class="p-3 border-t dark:border-gray-700 flex gap-2">
        <button onclick="bulkDelete()" class="text-sm px-3 py-1.5 bg-rose-600 text-white rounded-lg hover:bg-rose-500">Delete Selected</button>
        <button onclick="bulkReconcile()" class="text-sm px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500">Reconcile Selected</button>
        <button onclick="openBulkModal()" class="text-sm px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500">Edit Selected</button>
      </div>
    </div>
    <div id="import-status" class="text-sm"></div>
  `;

  renderTxRows(txs);
  populateTagFilter(txs);
}

function renderTxRows(txs) {
  const tbody = document.getElementById('tx-table-body');
  if (txs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No transactions match.</td></tr>`;
    return;
  }
  tbody.innerHTML = txs.map(tx => {
    const tagList = (tx.tags || '').split(',').filter(t => t.trim()).map(t => `<span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 mr-1">${escapeHtml(t.trim())}</span>`).join('');
    const isSplit = tx.splits && tx.splits.length > 0;
    const splitBadge = isSplit ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 ml-1">Split</span>` : '';
    const categoryDisplay = isSplit
      ? tx.splits.map(s => s.category ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mr-1" style="background:${safeColor(s.category.color)}20;color:${safeColor(s.category.color)}">${escapeHtml(s.category.name)}</span>` : '-').join('')
      : (tx.category ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium" style="background:${safeColor(tx.category.color)}20;color:${safeColor(tx.category.color)}">${escapeHtml(tx.category.name)}</span>` : '-');
    return `
    <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${tx.is_reconciled ? 'bg-emerald-50 dark:bg-emerald-900/20' : ''}" onclick="toggleTxDetails(${tx.id})">
      <td class="px-4 py-3"><input type="checkbox" class="tx-checkbox" value="${tx.id}" onclick="event.stopPropagation()"></td>
      <td class="px-4 py-3 whitespace-nowrap dark:text-gray-300">${formatDate(tx.date)}</td>
      <td class="px-4 py-3 dark:text-gray-300">
        <div>${escapeHtml(tx.description)}</div>
        ${tagList ? `<div class="mt-1">${tagList}</div>` : ''}
      </td>
      <td class="px-4 py-3">
        ${categoryDisplay}
        ${tx.transaction_type === 'transfer' ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400 ml-1">Transfer</span>` : ''}
        ${splitBadge}
      </td>
      <td class="px-4 py-3 text-right font-medium ${tx.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${tx.amount >= 0 ? '+' : ''}${formatMoney(tx.amount)}</td>
      <td class="px-4 py-3 text-right flex items-center justify-end gap-2">
        <button onclick="event.stopPropagation(); editTransaction(${tx.id})" class="text-gray-400 hover:text-blue-600 dark:hover:text-blue-400" title="Edit">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
        </button>
        <button onclick="event.stopPropagation(); deleteTransaction(${tx.id})" class="text-gray-400 hover:text-rose-600 dark:hover:text-rose-400">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
        </button>
      </td>
    </tr>
    ${(tx.notes || isSplit) ? `<tr id="tx-details-${tx.id}" class="hidden border-b dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
      <td colspan="6" class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 space-y-1">
        ${tx.notes ? `<div><span class="font-medium">Notes:</span> ${escapeHtml(tx.notes)}</div>` : ''}
        ${isSplit ? `<div><span class="font-medium">Splits:</span> ${tx.splits.map(s => `${s.category ? escapeHtml(s.category.name) : 'Uncategorized'}: ${formatMoney(s.amount)}`).join(', ')}</div>` : ''}
      </td>
    </tr>` : ''}
  `}).join('');
}

function toggleTxDetails(id) {
  const el = document.getElementById(`tx-details-${id}`);
  if (el) el.classList.toggle('hidden');
}

let currentTxs = [];

async function applyTxFilters() {
  const accountId = document.getElementById('tx-account-filter').value;
  const categoryId = document.getElementById('tx-category-filter').value;
  const tag = document.getElementById('tx-tag-filter').value;
  const q = document.getElementById('tx-search').value;
  const start = document.getElementById('tx-start-date').value;
  const end = document.getElementById('tx-end-date').value;

  const params = new URLSearchParams();
  params.set('limit', '200');
  if (accountId) params.set('account_id', accountId);
  if (categoryId) params.set('category_id', categoryId);
  if (tag) params.set('tag', tag);
  if (q) params.set('q', q);
  if (start) params.set('start_date', start);
  if (end) params.set('end_date', end);

  const txs = await apiGet('/api/transactions?' + params.toString());
  currentTxs = txs;
  renderTxRows(txs);
  populateTagFilter(txs);
}

function populateTagFilter(txs) {
  const allTags = new Set();
  txs.forEach(tx => {
    (tx.tags || '').split(',').forEach(t => { if (t.trim()) allTags.add(t.trim()); });
  });
  const sel = document.getElementById('tx-tag-filter');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">All tags</option>' + Array.from(allTags).sort().map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join('');
  sel.value = current;
}

function toggleSelectAll() {
  const all = document.getElementById('tx-select-all').checked;
  document.querySelectorAll('.tx-checkbox').forEach(cb => cb.checked = all);
}

async function bulkDelete() {
  const ids = Array.from(document.querySelectorAll('.tx-checkbox:checked')).map(cb => cb.value);
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} transactions?`)) return;
  await apiPost('/api/transactions/bulk-delete', { ids: ids.map(Number) });
  renderView('transactions');
}

async function bulkReconcile() {
  const ids = Array.from(document.querySelectorAll('.tx-checkbox:checked')).map(cb => cb.value);
  if (!ids.length) return;
  await apiPost('/api/transactions/bulk-reconcile', { ids: ids.map(Number) });
  renderView('transactions');
}

async function reconcileStatement(input) {
  const file = input.files[0];
  if (!file) return;
  const accountId = document.getElementById('tx-account-filter')?.value;
  if (!accountId) { alert('Pilih akun dulu di filter akun'); input.value = ''; return; }
  const autoMark = confirm('Tandai yang cocok sebagai reconciled otomatis? OK = ya, Cancel = preview saja.');
  const form = new FormData();
  form.append('file', file);
  const q = new URLSearchParams({ account_id: accountId, tolerance_days: '2', auto_mark: autoMark });
  const r = await apiFetch('/api/transactions/reconcile-statement?' + q.toString(), { method: 'POST', body: form });
  const result = await r.json();
  const status = document.getElementById('import-status');
  if (!r.ok) {
    status.textContent = 'Error: ' + (result.detail || 'Reconcile gagal');
  } else {
    status.textContent = `Cocok ${result.totals.matched} dari ${result.totals.statement_rows} baris${result.marked_reconciled ? ` (${result.marked_reconciled} ditandai)` : ''}.`;
    renderView('transactions');
  }
  input.value = '';
}

async function deleteTransaction(id) {
  if (!confirm('Delete this transaction?')) return;
  await apiDelete(`/api/transactions/${id}`);
  renderView('transactions');
}

// ============== TRANSACTION MODAL ==============
let modalAccounts = [];
let modalCategories = [];
let editingTxId = null;

async function openTxModal(prefill = {}) {
  const modal = document.getElementById('tx-modal');
  modal.classList.remove('hidden');

  // Load refs if needed
  if (!modalAccounts.length) modalAccounts = await apiGet('/api/accounts');
  if (!modalCategories.length) modalCategories = await apiGet('/api/categories');

  const accSel = document.getElementById('tx-account-select');
  accSel.innerHTML = modalAccounts.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');

  const catSel = document.getElementById('tx-category-select');
  catSel.innerHTML = `<option value="">-- None --</option>` + modalCategories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');

  // Reset split UI
  document.getElementById('tx-is-split').checked = false;
  toggleSplitMode();
  document.getElementById('tx-splits-list').innerHTML = '';

  // Defaults
  const today = new Date().toISOString().slice(0, 10);
  document.getElementById('tx-id').value = prefill.id || '';
  document.getElementById('tx-modal-title').textContent = prefill.id ? 'Edit Transaction' : 'Add Transaction';
  document.getElementById('tx-date').value = prefill.date || today;
  document.querySelector('#tx-form [name="amount"]').value = prefill.amount !== undefined ? Math.abs(prefill.amount) : '';
  document.querySelector('#tx-form [name="description"]').value = prefill.description || '';
  document.querySelector('#tx-form [name="account_id"]').value = prefill.account_id || modalAccounts[0]?.id || '';
  document.querySelector('#tx-form [name="category_id"]').value = prefill.category_id || '';
  document.querySelector('#tx-form [name="currency"]').value = prefill.currency || 'IDR';
  document.querySelector('#tx-form [name="notes"]').value = prefill.notes || '';
  document.querySelector('#tx-form [name="tags"]').value = prefill.tags || '';
  document.getElementById('tx-is-expense').checked = prefill.is_expense !== undefined ? prefill.is_expense : true;

  // Handle splits prefill
  if (prefill.splits && prefill.splits.length > 0) {
    document.getElementById('tx-is-split').checked = true;
    toggleSplitMode();
    prefill.splits.forEach(s => addSplitRow(s));
  } else if (prefill.id) {
    // Editing non-split: ensure at least one split row if they toggle later
    addSplitRow();
    // But hide it since split mode is off
    const list = document.getElementById('tx-splits-list');
    list.innerHTML = '';
  }

  editingTxId = prefill.id || null;
  refreshTemplateSelect();
  document.querySelector('#tx-form [name="description"]')?.focus();
}

function closeTxModal() {
  document.getElementById('tx-modal').classList.add('hidden');
  editingTxId = null;
}

function toggleSplitMode() {
  const isSplit = document.getElementById('tx-is-split').checked;
  document.getElementById('tx-single-category-wrap').classList.toggle('hidden', isSplit);
  document.getElementById('tx-splits-wrap').classList.toggle('hidden', !isSplit);
  if (isSplit && document.getElementById('tx-splits-list').children.length === 0) {
    addSplitRow();
    addSplitRow();
  }
  updateSplitTotal();
}

function addSplitRow(data = null) {
  const list = document.getElementById('tx-splits-list');
  const idx = list.children.length;
  const row = document.createElement('div');
  row.className = 'grid grid-cols-[1fr,auto,auto] gap-2 items-center';
  row.innerHTML = `
    <select class="tx-split-cat text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2">
      <option value="">-- Category --</option>
      ${modalCategories.map(c => `<option value="${c.id}" ${data && data.category_id == c.id ? 'selected' : ''}>${escapeHtml(c.name)}</option>`).join('')}
    </select>
    <input type="number" step="0.01" placeholder="Amount" class="tx-split-amt w-28 text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2" value="${data ? Math.abs(data.amount) : ''}">
    <button type="button" onclick="this.parentElement.remove(); updateSplitTotal();" class="text-gray-400 hover:text-rose-600">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
    </button>
  `;
  list.appendChild(row);
  row.querySelector('.tx-split-amt').addEventListener('input', updateSplitTotal);
  updateSplitTotal();
}

function updateSplitTotal() {
  const totalEl = document.getElementById('tx-split-total');
  const amts = Array.from(document.querySelectorAll('.tx-split-amt')).map(i => parseFloat(i.value) || 0);
  const total = amts.reduce((a, b) => a + b, 0);
  const mainAmt = parseFloat(document.querySelector('#tx-form [name="amount"]').value) || 0;
  const diff = Math.abs(mainAmt) - total;
  totalEl.textContent = `Total: ${total.toLocaleString()} / ${Math.abs(mainAmt).toLocaleString()} ${Math.abs(diff) < 0.01 ? '✓' : `(diff: ${diff.toLocaleString()})`}`;
  totalEl.className = `text-xs font-medium ${Math.abs(diff) < 0.01 ? 'text-emerald-600' : 'text-amber-600'}`;
}

async function saveTransaction(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  let amount = parseFloat(fd.get('amount'));
  const isExpense = fd.get('is_expense') === 'on';
  if (isExpense) amount = -Math.abs(amount);
  else amount = Math.abs(amount);

  const isSplit = document.getElementById('tx-is-split').checked;
  let splits = null;
  if (isSplit) {
    const splitRows = document.querySelectorAll('#tx-splits-list > div');
    splits = Array.from(splitRows).map(row => {
      const catId = row.querySelector('.tx-split-cat').value;
      const amt = parseFloat(row.querySelector('.tx-split-amt').value) || 0;
      return {
        category_id: catId ? parseInt(catId) : null,
        amount: isExpense ? -Math.abs(amt) : Math.abs(amt),
      };
    }).filter(s => s.category_id && s.amount !== 0);
    const splitTotal = splits.reduce((a, s) => a + Math.abs(s.amount), 0);
    if (Math.abs(splitTotal - Math.abs(amount)) > 0.01) {
      alert('Split amounts must add up to the transaction total.');
      return;
    }
  }

  const payload = {
    date: fd.get('date'),
    description: fd.get('description'),
    amount: amount,
    currency: fd.get('currency'),
    account_id: parseInt(fd.get('account_id')),
    category_id: isSplit ? null : (fd.get('category_id') ? parseInt(fd.get('category_id')) : null),
    notes: fd.get('notes') || '',
    tags: fd.get('tags') || '',
    transaction_type: isExpense ? 'expense' : 'income',
    splits: splits,
  };

  if (editingTxId) {
    await apiFetch(`/api/transactions/${editingTxId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } else {
    await apiPost('/api/transactions', payload);
  }
  closeTxModal();
  e.target.reset();
  if (currentView === 'transactions') renderView('transactions');
  else if (currentView === 'dashboard') renderView('dashboard');
}

async function editTransaction(id) {
  const tx = await apiGet(`/api/transactions/${id}`);
  if (!tx) return;
  openTxModal({
    id: tx.id,
    date: tx.date,
    amount: tx.amount,
    description: tx.description,
    account_id: tx.account_id,
    category_id: tx.category_id,
    currency: tx.currency,
    notes: tx.notes,
    tags: tx.tags,
    is_expense: tx.amount < 0,
    splits: tx.splits,
  });
}

// ============== TEMPLATES ==============
function getTemplates() {
  try { return JSON.parse(localStorage.getItem('tx_templates') || '[]'); }
  catch { return []; }
}

function setTemplates(tpls) {
  localStorage.setItem('tx_templates', JSON.stringify(tpls));
}

function saveAsTemplate() {
  const fd = new FormData(document.getElementById('tx-form'));
  const name = fd.get('description') || 'Unnamed';
  const tpl = {
    id: Date.now(),
    name,
    description: fd.get('description'),
    amount: fd.get('amount'),
    account_id: fd.get('account_id'),
    category_id: fd.get('category_id'),
    currency: fd.get('currency'),
    is_expense: document.getElementById('tx-is-expense').checked,
    notes: fd.get('notes') || '',
    tags: fd.get('tags') || '',
  };
  const tpls = getTemplates();
  tpls.push(tpl);
  setTemplates(tpls);
  refreshTemplateSelect();
  // Show feedback
  const sel = document.getElementById('tx-template-select');
  const old = sel.options[0].text;
  sel.options[0].text = 'Template saved!';
  setTimeout(() => sel.options[0].text = old, 1500);
}

function loadTemplate(id) {
  if (!id) return;
  const tpl = getTemplates().find(t => String(t.id) === String(id));
  if (!tpl) return;
  document.querySelector('#tx-form [name="description"]').value = tpl.description || '';
  document.querySelector('#tx-form [name="amount"]').value = tpl.amount || '';
  document.querySelector('#tx-form [name="account_id"]').value = tpl.account_id || '';
  document.querySelector('#tx-form [name="category_id"]').value = tpl.category_id || '';
  document.querySelector('#tx-form [name="currency"]').value = tpl.currency || 'IDR';
  document.querySelector('#tx-form [name="notes"]').value = tpl.notes || '';
  document.querySelector('#tx-form [name="tags"]').value = tpl.tags || '';
  document.getElementById('tx-is-expense').checked = tpl.is_expense !== false;
}

function refreshTemplateSelect() {
  const sel = document.getElementById('tx-template-select');
  const tpls = getTemplates();
  sel.innerHTML = `<option value="">-- ${tpls.length} template(s) --</option>` +
    tpls.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
}

// ============== BULK EDIT ==============
async function openBulkModal() {
  const ids = Array.from(document.querySelectorAll('.tx-checkbox:checked')).map(cb => cb.value);
  if (!ids.length) return;
  if (!modalCategories.length) modalCategories = await apiGet('/api/categories');
  const catSel = document.getElementById('bulk-category');
  catSel.innerHTML = `<option value="">-- No change --</option>` + modalCategories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
  document.getElementById('bulk-date').value = '';
  document.getElementById('bulk-modal').classList.remove('hidden');
}

function closeBulkModal() {
  document.getElementById('bulk-modal').classList.add('hidden');
}

async function applyBulkEdit() {
  const ids = Array.from(document.querySelectorAll('.tx-checkbox:checked')).map(cb => parseInt(cb.value));
  if (!ids.length) return;
  const categoryId = document.getElementById('bulk-category').value;
  const dateVal = document.getElementById('bulk-date').value;
  const payload = { ids };
  if (categoryId) payload.category_id = parseInt(categoryId);
  if (dateVal) payload.date = dateVal;
  if (!payload.category_id && !payload.date) { closeBulkModal(); return; }
  await apiPost('/api/transactions/bulk-update', payload);
  closeBulkModal();
  renderView('transactions');
}

// ============== TRANSFER ==============
async function openTransferModal() {
  const modal = document.getElementById('transfer-modal');
  modal.classList.remove('hidden');
  if (!modalAccounts.length) modalAccounts = await apiGet('/api/accounts');
  const fromSel = document.getElementById('transfer-from-account');
  const toSel = document.getElementById('transfer-to-account');
  const opts = modalAccounts.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
  fromSel.innerHTML = opts;
  toSel.innerHTML = opts;
  if (modalAccounts.length > 1) toSel.selectedIndex = 1;
  document.getElementById('transfer-date').value = new Date().toISOString().slice(0, 10);
}

function closeTransferModal() {
  document.getElementById('transfer-modal').classList.add('hidden');
}

async function saveTransfer(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const fromId = parseInt(fd.get('from_account_id'));
  const toId = parseInt(fd.get('to_account_id'));
  if (fromId === toId) { alert('From and To accounts must be different'); return; }
  await apiPost('/api/transactions/transfer', {
    from_account_id: fromId,
    to_account_id: toId,
    amount: parseFloat(fd.get('amount')),
    currency: fd.get('currency'),
    date: fd.get('date'),
    description: fd.get('description') || 'Transfer',
  });
  closeTransferModal();
  e.target.reset();
  renderView('transactions');
}

// ============== KEYBOARD SHORTCUTS ==============
document.addEventListener('keydown', (e) => {
  const tag = document.activeElement?.tagName;
  const isTyping = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

  // Ctrl+N -> Add transaction
  if (e.ctrlKey && (e.key === 'n' || e.key === 'N')) {
    e.preventDefault();
    openTxModal();
    return;
  }

  // Ctrl+S -> Save if modal open
  if (e.ctrlKey && (e.key === 's' || e.key === 'S')) {
    const modal = document.getElementById('tx-modal');
    if (!modal.classList.contains('hidden')) {
      e.preventDefault();
      document.getElementById('tx-form').dispatchEvent(new Event('submit'));
    }
    return;
  }

  // / -> Focus search
  if (e.key === '/' && !isTyping) {
    e.preventDefault();
    const search = document.getElementById('tx-search');
    if (search) search.focus();
    return;
  }

  // C -> Calendar
  if (e.key === 'c' && !isTyping) {
    e.preventDefault();
    navigate('calendar');
    return;
  }

  // Escape -> Close modals
  if (e.key === 'Escape') {
    closeTxModal();
    closeBulkModal();
    closeTransferModal();
  }
});

// ============== ACCOUNTS ==============
async function renderAccounts(container) {
  const accounts = await apiGet('/api/accounts');
  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4 mb-4">
      <form onsubmit="createAccount(event)" class="flex gap-3 flex-wrap">
        <input name="name" placeholder="Account name" class="flex-1 min-w-[120px] border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <select name="type" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="checking">Checking</option>
          <option value="savings">Savings</option>
          <option value="cash">Cash</option>
          <option value="investment">Investment</option>
        </select>
        <select name="currency" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="IDR">IDR</option>
          <option value="USD">USD</option>
          <option value="AUD">AUD</option>
        </select>
        <button type="submit" class="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">Add</button>
      </form>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      ${accounts.map(a => `
        <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between">
              <h4 class="font-semibold text-sm dark:text-gray-200">${escapeHtml(a.name)}</h4>
              <span class="text-xs text-gray-400 uppercase">${escapeHtml(a.type)}</span>
            </div>
            <p class="text-xl font-bold mt-2 dark:text-gray-100">${formatMoney(a.initial_balance, a.currency)}</p>
            <p class="text-xs text-gray-400">${escapeHtml(a.currency)}</p>
          </div>
          <button onclick="deleteAccount(${a.id})" class="mt-4 text-xs text-rose-600 hover:underline text-left">Delete</button>
        </div>
      `).join('')}
    </div>
  `;
}

async function createAccount(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await apiPost('/api/accounts', {
    name: fd.get('name'), type: fd.get('type'), currency: fd.get('currency'), initial_balance: 0,
  });
  renderView('accounts');
}

async function deleteAccount(id) {
  if (!confirm('Delete this account?')) return;
  await apiDelete(`/api/accounts/${id}`);
  renderView('accounts');
}

// ============== BUDGETS ==============
async function renderBudgets(container) {
  const now = new Date();
  const [categories, budgets] = await Promise.all([
    apiGet('/api/categories'),
    apiGet(`/api/budgets?year=${now.getFullYear()}&month=${now.getMonth()+1}`),
  ]);

  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4 mb-4">
      <form onsubmit="createBudget(event)" class="flex gap-3 flex-wrap">
        <select name="category_id" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
          <option value="">Select category</option>
          ${categories.filter(c => c.type === 'expense').map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('')}
        </select>
        <input name="amount" type="number" placeholder="Budget amount" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <select name="currency" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="IDR">IDR</option>
          <option value="USD">USD</option>
          <option value="AUD">AUD</option>
        </select>
        <label class="flex items-center gap-2 text-sm dark:text-gray-300">
          <input type="checkbox" name="rollover" class="rounded"> Rollover unused
        </label>
        <button type="submit" class="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">Set Budget</button>
      </form>
    </div>
    <div class="space-y-4">
      ${budgets.length === 0 ? '<p class="text-gray-400 dark:text-gray-500 text-sm">No budgets set for this month.</p>' : budgets.map(b => {
        const pct = Math.min(100, (Math.abs(Number(b.spent || 0)) / Number(b.amount)) * 100);
        const remaining = Number(b.amount) - Math.abs(Number(b.spent || 0));
        let barColor = 'bg-blue-600';
        if (pct > 95) barColor = 'bg-rose-500';
        else if (pct >= 75) barColor = 'bg-amber-500';
        return `
        <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-4 shadow-sm">
          <div class="flex items-center justify-between mb-2">
            <span class="font-medium text-sm dark:text-gray-200">${escapeHtml(b.category?.name ?? "") || 'Unknown'}</span>
            <span class="text-xs text-gray-500 dark:text-gray-400">${formatMoney(b.spent || 0)} / ${formatMoney(b.amount, b.currency)}</span>
          </div>
          <div class="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2">
            <div class="${barColor} h-2 rounded-full transition-all" style="width: ${pct}%"></div>
          </div>
          <div class="flex items-center justify-between mt-1">
            <span class="text-xs ${pct > 90 ? 'text-rose-600 font-medium' : 'text-gray-400'}">${pct.toFixed(0)}% used · ${remaining >= 0 ? formatMoney(remaining) + ' remaining' : formatMoney(Math.abs(remaining)) + ' over budget'}</span>
            ${b.rollover ? `<span class="text-xs text-gray-400">Rollover enabled</span>` : ''}
          </div>
        </div>
      `}).join('')}
    </div>
  `;
}

async function createBudget(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const now = new Date();
  await apiPost('/api/budgets', {
    year: now.getFullYear(), month: now.getMonth() + 1,
    category_id: parseInt(fd.get('category_id')),
    amount: parseFloat(fd.get('amount')),
    currency: fd.get('currency'),
    rollover: fd.has('rollover'),
  });
  renderView('budgets');
}

// ============== CATEGORIES ==============
async function renderCategories(container) {
  const categories = await apiGet('/api/categories');
  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4 mb-4">
      <form onsubmit="createCategory(event)" class="flex gap-3 flex-wrap">
        <input name="name" placeholder="Category name" class="flex-1 min-w-[120px] border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <select name="type" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="expense">Expense</option>
          <option value="income">Income</option>
          <option value="transfer">Transfer</option>
        </select>
        <input name="keywords" placeholder="Keywords (comma separated)" class="flex-1 min-w-[200px] border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
        <button type="submit" class="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">Add</button>
      </form>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm overflow-hidden">
      <table class="w-full text-sm text-left">
        <thead class="bg-gray-50 dark:bg-gray-700 text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr><th class="px-4 py-3">Name</th><th class="px-4 py-3">Type</th><th class="px-4 py-3">Keywords</th></tr>
        </thead>
        <tbody>
          ${categories.map(c => `
            <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
              <td class="px-4 py-3 flex items-center gap-2 dark:text-gray-300">
                <span class="w-3 h-3 rounded-full inline-block" style="background:${safeColor(c.color)}"></span>
                ${escapeHtml(c.name)}
              </td>
              <td class="px-4 py-3 capitalize dark:text-gray-300">${escapeHtml(c.type)}</td>
              <td class="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs">${escapeHtml(c.keywords || '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

async function createCategory(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await apiPost('/api/categories', {
    name: fd.get('name'), type: fd.get('type'), keywords: fd.get('keywords'),
    color: '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6, '0'),
  });
  renderView('categories');
}

// ============== GOALS ==============
async function renderGoals(container) {
  const goals = await apiGet('/api/goals');
  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4 mb-4">
      <form onsubmit="createGoal(event)" class="flex gap-3 flex-wrap">
        <input name="name" placeholder="Goal name (e.g. Emergency Fund)" class="flex-1 min-w-[150px] border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="target_amount" type="number" placeholder="Target" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="current_amount" type="number" placeholder="Current (optional)" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
        <select name="currency" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="IDR">IDR</option>
          <option value="USD">USD</option>
          <option value="AUD">AUD</option>
        </select>
        <button type="submit" class="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">Add Goal</button>
      </form>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      ${goals.length === 0 ? '<p class="text-gray-400 dark:text-gray-500 text-sm col-span-full">No goals yet.</p>' : goals.map(g => {
        const pct = Math.min(100, (Number(g.current_amount) / Number(g.target_amount)) * 100);
        return `
        <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-4 shadow-sm">
          <h4 class="font-semibold text-sm dark:text-gray-200">${escapeHtml(g.name)}</h4>
          <p class="text-2xl font-bold mt-1 dark:text-gray-100">${formatMoney(g.current_amount, g.currency)} <span class="text-sm font-normal text-gray-400">/ ${formatMoney(g.target_amount, g.currency)}</span></p>
          <div class="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-2 mt-3">
            <div class="bg-emerald-500 h-2 rounded-full transition-all" style="width: ${pct}%"></div>
          </div>
          <p class="text-xs text-gray-400 mt-1">${pct.toFixed(0)}% complete</p>
          <button onclick="deleteGoal(${g.id})" class="mt-3 text-xs text-rose-600 hover:underline">Delete</button>
        </div>
      `}).join('')}
    </div>
  `;
}

async function createGoal(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await apiPost('/api/goals', {
    name: fd.get('name'),
    target_amount: parseFloat(fd.get('target_amount')),
    current_amount: parseFloat(fd.get('current_amount') || '0'),
    currency: fd.get('currency'),
  });
  renderView('goals');
}

async function deleteGoal(id) {
  if (!confirm('Delete this goal?')) return;
  await apiDelete(`/api/goals/${id}`);
  renderView('goals');
}

// ============== INVESTMENTS ==============
async function renderInvest(container) {
  const [holdings, accounts, alerts, alloc] = await Promise.all([apiGet('/api/holdings'), apiGet('/api/accounts'), apiGet('/api/holdings/alerts/list?unread_only=true').catch(() => []), apiGet('/api/holdings/allocation').catch(() => ({total: 0, slices: []}))]);
  const total = holdings.reduce((a, h) => a + Number(h.value), 0);
  const pnl = holdings.reduce((a, h) => a + Number(h.pnl), 0);
  syncAppBadge(alerts.length);
  container.innerHTML = `
    ${alerts.length ? `<div class="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl p-4 mb-4 text-sm">
      <div class="flex items-center justify-between mb-2">
        <span class="font-semibold text-amber-800 dark:text-amber-300">${alerts.length} alert${alerts.length > 1 ? 's' : ''} harga tercapai</span>
        <button onclick="markAllAlertsRead()" class="text-xs text-amber-700 dark:text-amber-400 underline">Tandai dibaca</button>
      </div>
      ${alerts.slice(0, 5).map(a => `<div class="text-amber-700 dark:text-amber-400">${escapeHtml(a.symbol)} ${a.direction === 'above' ? '>=' : '<='} ${escapeHtml(String(a.target))} <button class="underline" onclick="markAlertRead(${a.id})">OK</button></div>`).join('')}
    </div>` : ''}
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-4 shadow-sm">
        <p class="text-xs text-gray-500 uppercase">Portfolio Value</p>
        <p class="text-2xl font-bold dark:text-gray-100 tabular-nums">${formatMoney(total)}</p>
        <div class="mt-2 h-[180px]"><canvas id="allocChart"></canvas></div>
      </div>
      <div class="grid grid-cols-1 gap-4 md:col-span-3">
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-4 shadow-sm">
        <p class="text-xs text-gray-500 uppercase">Unrealized P/L</p>
        <p class="text-2xl font-bold ${pnl >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${pnl >= 0 ? '+' : ''}${formatMoney(pnl)}</p>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-4 shadow-sm">
        <p class="text-xs text-gray-500 uppercase">Holdings</p>
        <p class="text-2xl font-bold dark:text-gray-100">${holdings.length}</p>
      </div>
      </div>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4 mb-4">
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 class="text-sm font-semibold dark:text-gray-200">Add / Refresh</h3>
        <button onclick="refreshAllPrices()" class="text-sm px-3 py-1.5 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-transform enabled:active:scale-[0.96]">Refresh prices</button>
        <button onclick="downloadHoldingsPdf('id')" class="text-sm px-3 py-1.5 border dark:border-gray-600 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">PDF ID</button>
        <button onclick="downloadHoldingsPdf('en')" class="text-sm px-3 py-1.5 border dark:border-gray-600 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">PDF EN</button>
        <button onclick="togglePushSubscription()" class="text-sm px-3 py-1.5 border dark:border-gray-600 dark:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">Aktifkan notifikasi push</button>
      </div>
      <form onsubmit="createHolding(event)" class="flex gap-3 flex-wrap">
        <input name="symbol" placeholder="Symbol (e.g. BBCA)" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="units" type="number" step="any" placeholder="Units" class="w-28 border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="cost_basis" type="number" step="any" placeholder="Avg cost" class="w-32 border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="current_price" type="number" step="any" placeholder="Price now" class="w-32 border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="alert_above" type="number" step="any" placeholder="Alert >= (opsional)" class="w-36 border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
        <input name="alert_below" type="number" step="any" placeholder="Alert <= (opsional)" class="w-36 border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
        <select name="account_id" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          ${accounts.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('')}
        </select>
        <button type="submit" class="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 transition-transform enabled:active:scale-[0.96]">Add Holding</button>
      </form>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm overflow-x-auto">
      <table class="w-full text-sm text-left">
        <thead class="bg-gray-50 dark:bg-gray-700 text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr><th class="px-4 py-3">Symbol</th><th class="px-4 py-3 text-right">Units</th><th class="px-4 py-3 text-right">Avg Cost</th><th class="px-4 py-3 text-right">Price</th><th class="px-4 py-3">Trend</th><th class="px-4 py-3 text-right">Value</th><th class="px-4 py-3 text-right">P/L</th><th class="px-4 py-3"></th></tr>
        </thead>
        <tbody>
          ${holdings.length === 0 ? '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-400">No holdings yet.</td></tr>' : holdings.map(h => `
            <tr class="border-b dark:border-gray-700">
              <td class="px-4 py-3 font-medium dark:text-gray-200">${escapeHtml(h.symbol)}</td>
              <td class="px-4 py-3 text-right dark:text-gray-300">${h.units}</td>
              <td class="px-4 py-3 text-right dark:text-gray-300">${formatMoney(h.cost_basis, h.currency)}</td>
              <td class="px-4 py-3 text-right dark:text-gray-300">${formatMoney(h.current_price, h.currency)}</td>
              <td class="px-4 py-3"><canvas class="sparkline" data-holding="${h.id}" width="100" height="28"></canvas>${h.alert ? `<div class="text-xs font-semibold text-amber-600 mt-1">${escapeHtml(h.alert)}</div>` : ''}</td>
              <td class="px-4 py-3 text-right font-medium dark:text-gray-200">${formatMoney(h.value, h.currency)}</td>
              <td class="px-4 py-3 text-right font-medium ${Number(h.pnl) >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${formatMoney(h.pnl, h.currency)}</td>
              <td class="px-4 py-3 text-right flex items-center justify-end gap-2">
          <button onclick="refreshHolding(${h.id})" class="text-gray-400 hover:text-emerald-600" title="Refresh price">&#8635;</button>
          <button onclick="deleteHolding(${h.id})" class="text-gray-400 hover:text-rose-600">Delete</button>
        </td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;
  loadSparklines();
  drawAllocChart(alloc);
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function togglePushSubscription() {
  try {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      alert('Push tidak didukung browser ini');
      return;
    }
    const cfg = await apiGet('/api/holdings/push/vapid-key');
    if (!cfg.configured) {
      alert('Push belum dikonfigurasi server (VAPID)');
      return;
    }
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (sub) {
      await sub.unsubscribe();
      await apiPost('/api/holdings/push/unsubscribe', {
        endpoint: sub.endpoint,
        p256dh: 'x',
        auth: 'xxxxx',
      }).catch(() => {});
      alert('Notifikasi push dimatikan');
      return;
    }
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      alert('Izin notifikasi ditolak');
      return;
    }
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(cfg.publicKey),
    });
    const keys = sub.toJSON().keys || {};
    await apiPost('/api/holdings/push/subscribe', {
      endpoint: sub.endpoint,
      p256dh: keys.p256dh || '',
      auth: keys.auth || '',
    });
    alert('Notifikasi push aktif');
  } catch (e) {
    alert('Push gagal: ' + e.message);
  }
}

async function createHolding(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await apiPost('/api/holdings', {
    symbol: fd.get('symbol'),
    units: parseFloat(fd.get('units')),
    cost_basis: parseFloat(fd.get('cost_basis')),
    current_price: parseFloat(fd.get('current_price')),
    account_id: parseInt(fd.get('account_id')),
    currency: 'IDR',
    alert_above: fd.get('alert_above') ? parseFloat(fd.get('alert_above')) : null,
    alert_below: fd.get('alert_below') ? parseFloat(fd.get('alert_below')) : null,
  });
  renderView('invest');
}

async function deleteHolding(id) {
  if (!confirm('Delete this holding?')) return;
  await apiDelete(`/api/holdings/${id}`);
  renderView('invest');
}

async function refreshHolding(id) {
  const r = await apiPost(`/api/holdings/${id}/refresh`, {});
  if (!r.ok && r.detail) alert('Refresh gagal: ' + r.detail);
  renderView('invest');
}

async function refreshAllPrices() {
  await apiPost('/api/holdings/refresh-all', {});
  renderView('invest');
}

async function downloadHoldingsPdf(lang = 'id') {
  const r = await apiFetch(`/api/reports/holdings?lang=${lang}`);
  if (!r.ok) { alert('Export PDF gagal, coba lagi.'); return; }
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `holdings_${lang}.pdf`;
  a.click();
}

function syncAppBadge(count) {
  try {
    if ('setAppBadge' in navigator && navigator.setAppBadge) {
      if (count > 0) navigator.setAppBadge(count).catch(() => {});
      else if (navigator.clearAppBadge) navigator.clearAppBadge().catch(() => {});
    }
  } catch { /* badge unsupported — silent */ }
  const base = 'Reign';
  document.title = count > 0 ? `(${count}) ${base}` : base;
}

async function markAlertRead(id) {
  await apiPost(`/api/holdings/alerts/${id}/read`, {});
  renderView('invest');
}

async function markAllAlertsRead() {
  await apiPost('/api/holdings/alerts/read-all', {});
  renderView('invest');
}

const ALLOC_COLORS = ['#2563eb','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#ec4899','#14b8a6'];

async function renderSankey() {
  const el = document.getElementById('sankey');
  if (!el) return;
  try {
    const now = new Date();
    const d = await apiGet(`/api/reports/sankey?year=${now.getFullYear()}&month=${now.getMonth()+1}`);
    if (!d.links.length) {
      el.innerHTML = '<p class="text-sm text-gray-400">Belum ada arus kas bulan ini.</p>';
      return;
    }
    const outs = d.links.filter(l => l.target.startsWith('out:'));
    const saved = d.links.find(l => l.target === 'saved');
    const total = Math.max(Number(d.total_in), 0.0001);
    const H = 26;
    const row = (label, val, color, wPct) => `
      <div class="flex items-center gap-2 mb-1.5">
        <span class="text-xs text-gray-500 dark:text-gray-400 w-32 truncate" title="${escapeHtml(label)}">${escapeHtml(label)}</span>
        <div class="flex-1 h-[${H}px] bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
          <div class="h-full rounded" style="width:${wPct}%;background:${color}"></div>
        </div>
        <span class="text-xs font-medium dark:text-gray-200 w-24 text-right tabular-nums">${formatMoney(val)}</span>
      </div>`;
    el.innerHTML = `
      <div class="min-w-[320px]">
        <p class="text-xs font-semibold text-emerald-700 dark:text-emerald-400 mb-2">Pemasukan ${formatMoney(d.total_in)}</p>
        ${outs.map(l => {
          const name = l.target.slice(4);
          const pct = Math.max((Number(l.value) / total) * 100, 1.5);
          return row(name, l.value, '#f43f5e', pct.toFixed(1));
        }).join('')}
        ${saved ? row('Sisa', saved.value, '#10b981', Math.max((Number(saved.value) / total) * 100, 1.5).toFixed(1)) : ''}
      </div>`;
  } catch {
    el.innerHTML = '<p class="text-sm text-gray-400">Sankey gagal dimuat.</p>';
  }
}

function drawAllocChart(alloc) {
  const el = document.getElementById('allocChart');
  if (!el || typeof Chart === 'undefined') return;
  const slices = (alloc && alloc.slices) || [];
  charts.push(new Chart(el.getContext('2d'), {
    type: 'doughnut',
    data: {
      labels: slices.map(s => s.symbol),
      datasets: [{
        data: slices.map(s => Number(s.value)),
        backgroundColor: slices.map((_, i) => ALLOC_COLORS[i % ALLOC_COLORS.length]),
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { boxWidth: 12, color: document.documentElement.classList.contains('dark') ? '#9ca3af' : '#6b7280' } },
        tooltip: { callbacks: { label: (c) => ` ${c.label}: ${formatMoney(c.parsed)} (${(slices[c.dataIndex].weight * 100).toFixed(1)}%)` } },
      },
    },
  }));
}

function drawSparkline(canvas, prices) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, hgt = canvas.height;
  ctx.clearRect(0, 0, w, hgt);
  if (!prices || prices.length < 2) return;
  const min = Math.min(...prices), max = Math.max(...prices);
  const span = max - min || 1;
  const up = prices[prices.length - 1] >= prices[0];
  ctx.strokeStyle = up ? '#10b981' : '#f43f5e';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  prices.forEach((p, i) => {
    const x = (i / (prices.length - 1)) * (w - 4) + 2;
    const y = hgt - 3 - ((p - min) / span) * (hgt - 6);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

async function loadSparklines() {
  const els = document.querySelectorAll('canvas.sparkline[data-holding]');
  await Promise.all(Array.from(els).map(async (el) => {
    try {
      const data = await apiGet(`/api/holdings/${el.dataset.holding}/history?limit=30`);
      drawSparkline(el, (data.points || []).map(p => Number(p.price)));
    } catch { /* offline: leave blank */ }
  }));
}

// ============== FORECAST ==============
async function renderForecast(container) {
  const data = await apiGet('/api/forecast?currency=IDR');
  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-5 shadow-sm">
      <h3 class="text-sm font-semibold mb-4 dark:text-gray-200">3-Month Cash Flow Forecast</h3>
      <div id="forecast-chart-wrapper" class="min-h-[300px]">
        <canvas id="forecastChart"></canvas>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
        ${data.months.map(m => `
          <div class="border dark:border-gray-700 rounded-lg p-4">
            <p class="text-xs text-gray-500 dark:text-gray-400 uppercase">${escapeHtml(m.label)}</p>
            <p class="text-lg font-bold ${m.net >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${m.net >= 0 ? '+' : ''}${formatMoney(m.net)}</p>
            <p class="text-xs text-gray-400">Income: ${formatMoney(m.income)} · Exp: ${formatMoney(Math.abs(m.expense))}</p>
          </div>
        `).join('')}
      </div>
      ${data.recurring.length > 0 ? `
      <div class="mt-6">
        <h4 class="text-sm font-semibold mb-2 dark:text-gray-200">Upcoming Recurring</h4>
        <div class="space-y-2">
          ${data.recurring.map(r => `
            <div class="flex items-center justify-between py-2 border-b dark:border-gray-700 text-sm">
              <span class="dark:text-gray-300">${escapeHtml(r.description)}</span>
              <span class="font-medium ${r.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${r.amount >= 0 ? '+' : ''}${formatMoney(r.amount)}</span>
            </div>
          `).join('')}
        </div>
      </div>` : ''}
    </div>
  `;

  if (data.months && data.months.length > 0) {
    const ctx = document.getElementById('forecastChart').getContext('2d');
    const isDark = document.documentElement.classList.contains('dark');
    const gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)';
    const textColor = isDark ? '#9ca3af' : '#6b7280';
    charts.push(new Chart(ctx, {
      type: 'bar',
      data: {
        labels: data.months.map(m => m.label),
        datasets: [
          { label: 'Income', data: data.months.map(m => Number(m.income)), backgroundColor: '#10b981' },
          { label: 'Expense', data: data.months.map(m => Math.abs(Number(m.expense))), backgroundColor: '#f43f5e' },
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: textColor } } },
        scales: {
          x: { grid: { color: gridColor }, ticks: { color: textColor } },
          y: { grid: { color: gridColor }, ticks: { color: textColor } }
        }
      }
    }));
  }
}

// ============== CALENDAR ==============
let calendarYear, calendarMonth;

async function renderCalendar(container) {
  const now = new Date();
  if (!calendarYear) { calendarYear = now.getFullYear(); calendarMonth = now.getMonth(); }

  const startOfMonth = new Date(calendarYear, calendarMonth, 1);
  const endOfMonth = new Date(calendarYear, calendarMonth + 1, 0);
  const daysInMonth = endOfMonth.getDate();
  const startDay = startOfMonth.getDay(); // 0=Sun

  const [txs] = await Promise.all([
    apiGet(`/api/transactions?start_date=${startOfMonth.toISOString().slice(0,10)}&end_date=${endOfMonth.toISOString().slice(0,10)}&limit=500`),
  ]);

  // Group transactions by day
  const dayMap = {};
  for (let d = 1; d <= daysInMonth; d++) dayMap[d] = { income: 0, expense: 0 };
  txs.forEach(tx => {
    const day = new Date(tx.date).getDate();
    if (!dayMap[day]) return;
    if (tx.transaction_type === 'transfer') return;
    if (tx.amount > 0) dayMap[day].income += Number(tx.amount);
    else dayMap[day].expense += Math.abs(Number(tx.amount));
  });

  const monthName = startOfMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4">
      <div class="flex items-center justify-between mb-4">
        <button onclick="changeCalendarMonth(-1)" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
          <svg class="w-5 h-5 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        </button>
        <h3 class="text-lg font-semibold dark:text-gray-200">${monthName}</h3>
        <button onclick="changeCalendarMonth(1)" class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700">
          <svg class="w-5 h-5 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        </button>
      </div>
      <div class="grid grid-cols-7 gap-1 mb-2 text-center">
        ${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => `<div class="text-xs font-medium text-gray-500 dark:text-gray-400 py-1">${d}</div>`).join('')}
      </div>
      <div class="grid grid-cols-7 gap-1">
        ${Array(startDay).fill('<div></div>').join('')}
        ${Array.from({length: daysInMonth}, (_, i) => {
          const day = i + 1;
          const data = dayMap[day];
          let dotColor = 'bg-gray-300 dark:bg-gray-600';
          if (data.income > 0 && data.expense === 0) dotColor = 'bg-emerald-500';
          else if (data.expense > 0 && data.income === 0) dotColor = 'bg-rose-500';
          else if (data.income > 0 && data.expense > 0) {
            dotColor = data.income >= data.expense ? 'bg-emerald-500' : 'bg-rose-500';
          }
          const isToday = day === now.getDate() && calendarMonth === now.getMonth() && calendarYear === now.getFullYear();
          return `
          <div onclick="showDayTransactions(${day})" class="aspect-square border dark:border-gray-700 rounded-lg p-1 flex flex-col items-center justify-start cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 ${isToday ? 'ring-2 ring-blue-500' : ''}">
            <span class="text-xs font-medium dark:text-gray-300">${day}</span>
            ${data.income > 0 || data.expense > 0 ? `<span class="w-2 h-2 rounded-full ${dotColor} mt-1"></span>` : ''}
          </div>`;
        }).join('')}
      </div>
      <div class="flex items-center gap-4 mt-4 text-xs text-gray-500 dark:text-gray-400">
        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-emerald-500"></span> Income</span>
        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-rose-500"></span> Expense</span>
        <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600"></span> Neutral</span>
      </div>
    </div>
    <div id="day-panel" class="hidden mt-4 bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4">
      <div class="flex items-center justify-between mb-3">
        <h4 class="text-sm font-semibold dark:text-gray-200" id="day-panel-title">Transactions</h4>
        <button onclick="closeDayPanel()" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <div id="day-panel-content" class="space-y-2"></div>
    </div>
  `;
}

function changeCalendarMonth(delta) {
  calendarMonth += delta;
  if (calendarMonth > 11) { calendarMonth = 0; calendarYear++; }
  if (calendarMonth < 0) { calendarMonth = 11; calendarYear--; }
  renderView('calendar');
}

async function showDayTransactions(day) {
  const dateStr = `${calendarYear}-${String(calendarMonth+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
  const txs = await apiGet(`/api/transactions?start_date=${dateStr}&end_date=${dateStr}&limit=100`);
  document.getElementById('day-panel').classList.remove('hidden');
  document.getElementById('day-panel-title').textContent = `Transactions for ${formatDate(dateStr)}`;
  const content = document.getElementById('day-panel-content');
  if (txs.length === 0) {
    content.innerHTML = '<p class="text-sm text-gray-400">No transactions.</p>';
  } else {
    content.innerHTML = txs.map(tx => `
      <div class="flex items-center justify-between py-2 border-b dark:border-gray-700 last:border-0">
        <div>
          <p class="text-sm font-medium dark:text-gray-200">${escapeHtml(tx.description)}</p>
          <p class="text-xs text-gray-400 dark:text-gray-500">${escapeHtml(tx.category?.name || 'Uncategorized')} ${tx.tags ? '· ' + escapeHtml(tx.tags) : ''}</p>
        </div>
        <span class="text-sm font-semibold ${tx.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${tx.amount >= 0 ? '+' : ''}${formatMoney(tx.amount)}</span>
      </div>
    `).join('');
  }
}

function closeDayPanel() {
  document.getElementById('day-panel').classList.add('hidden');
}

// ============== RECURRING ==============
async function renderRecurring(container) {
  const [recs, accounts, categories] = await Promise.all([
    apiGet('/api/recurring'),
    apiGet('/api/accounts'),
    apiGet('/api/categories'),
  ]);

  container.innerHTML = `
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm p-4 mb-4">
      <form onsubmit="createRecurring(event)" class="flex gap-3 flex-wrap">
        <input name="description" placeholder="Description (e.g. Netflix)" class="flex-1 min-w-[150px] border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="amount" type="number" step="0.01" placeholder="Amount" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <input name="day_of_month" type="number" min="1" max="31" placeholder="Day" class="w-20 border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm" required>
        <select name="account_id" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          ${accounts.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('')}
        </select>
        <select name="category_id" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="">-- Category --</option>
          ${categories.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('')}
        </select>
        <select name="currency" class="border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
          <option value="IDR">IDR</option>
          <option value="USD">USD</option>
          <option value="AUD">AUD</option>
        </select>
        <button type="submit" class="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">Add</button>
      </form>
    </div>
    <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 shadow-sm overflow-hidden">
      <table class="w-full text-sm text-left">
        <thead class="bg-gray-50 dark:bg-gray-700 text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr><th class="px-4 py-3">Description</th><th class="px-4 py-3">Amount</th><th class="px-4 py-3">Day</th><th class="px-4 py-3">Category</th><th class="px-4 py-3">Status</th><th class="px-4 py-3"></th></tr>
        </thead>
        <tbody>
          ${recs.length === 0 ? `<tr><td colspan="6" class="px-4 py-8 text-center text-gray-400 dark:text-gray-500">No recurring transactions.</td></tr>` : recs.map(r => `
            <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
              <td class="px-4 py-3 dark:text-gray-300">${escapeHtml(r.description)}</td>
              <td class="px-4 py-3 font-medium ${r.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${r.amount >= 0 ? '+' : ''}${formatMoney(r.amount)}</td>
              <td class="px-4 py-3 dark:text-gray-300">Day ${r.day_of_month}</td>
              <td class="px-4 py-3">${r.category ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium" style="background:${safeColor(r.category.color)}20;color:${safeColor(r.category.color)}">${escapeHtml(r.category.name)}</span>` : '-'}</td>
              <td class="px-4 py-3"><span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${r.active ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'}">${r.active ? 'Active' : 'Inactive'}</span></td>
              <td class="px-4 py-3 text-right">
                <button onclick="deleteRecurring(${r.id})" class="text-gray-400 hover:text-rose-600 dark:hover:text-rose-400">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

async function createRecurring(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await apiPost('/api/recurring', {
    description: fd.get('description'),
    amount: parseFloat(fd.get('amount')),
    day_of_month: parseInt(fd.get('day_of_month')),
    account_id: parseInt(fd.get('account_id')),
    category_id: fd.get('category_id') ? parseInt(fd.get('category_id')) : null,
    currency: fd.get('currency'),
    active: true,
  });
  renderView('recurring');
}

async function deleteRecurring(id) {
  if (!confirm('Delete this recurring transaction?')) return;
  await apiDelete(`/api/recurring/${id}`);
  renderView('recurring');
}

// ============== IMPORT / EXPORT ==============
async function importCSV(input) {
  const file = input.files[0];
  if (!file) return;

  // Preview first
  const previewForm = new FormData();
  previewForm.append('file', file);
  const pr = await apiFetch('/api/transactions/import-preview', { method: 'POST', body: previewForm });
  const preview = await pr.json();
  if (!pr.ok) {
    alert('CSV parse error: ' + (preview.detail || 'Unknown'));
    return;
  }

  const accounts = await apiGet('/api/accounts');
  const accountId = accounts[0]?.id;
  if (!accountId) { alert('Create an account first'); return; }

  const previewHTML = preview.preview.map((row, i) => `
    <tr class="border-b dark:border-gray-700">
      <td class="px-3 py-2 text-xs dark:text-gray-300">${escapeHtml(row.date)}</td>
      <td class="px-3 py-2 text-xs dark:text-gray-300">${escapeHtml(row.description)}</td>
      <td class="px-3 py-2 text-xs font-medium ${row.amount >= 0 ? 'text-emerald-600' : 'text-rose-600'}">${formatMoney(row.amount)}</td>
    </tr>
  `).join('');

  const confirmed = confirm(`Detected ${preview.total} transactions (${preview.format} format).\n\nFirst 10 rows preview:\n${preview.preview.map(r => `${r.date} | ${escapeHtml(r.description)} | ${r.amount}`).join('\n')}\n\nImport to account "${escapeHtml(accounts[0]?.name ?? '')}"?`);
  if (!confirmed) return;

  const form = new FormData();
  form.append('file', file);
  const r = await apiFetch(`/api/transactions/import?account_id=${accountId}`, { method: 'POST', body: form });
  const result = await r.json();
  const status = document.getElementById('import-status');
  if (r.ok) {
    status.textContent = '✓ ' + result.message;
    renderView('transactions');
  } else {
    status.textContent = 'Error: ' + (result.detail || 'Import failed');
  }
}

function exportTransactions(format) {
  const url = `/api/transactions/export/${format}`;
  const a = document.createElement('a');
  a.href = API + url;
  a.download = `transactions.${format}`;
  a.click();
}

// ============== REPORT ==============
async function generateReport() {
  const now = new Date();
  const url = `/api/reports/monthly?year=${now.getFullYear()}&month=${now.getMonth()+1}&currency=IDR`;
  const r = await apiFetch(url);
  if (!r.ok) { alert('Failed to generate report'); return; }
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `report_${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}_IDR.pdf`;
  a.click();
}

// ============== SETTINGS ==============
async function renderSettings(container) {
  const settings = await apiGet('/api/settings');
  const enabled = (settings.auto_backup_enabled || 'false').toLowerCase() === 'true';
  const interval = settings.auto_backup_interval_days || '7';
  const compress = (settings.auto_backup_compress || 'true').toLowerCase() === 'true';
  const digest = (settings.digest_enabled || 'false').toLowerCase() === 'true';
  const lastRun = settings.auto_backup_last_run || 'Never';

  container.innerHTML = `
    <div class="max-w-xl mx-auto space-y-6">
      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-6 shadow-sm">
        <h3 class="text-sm font-semibold mb-4 dark:text-gray-200 flex items-center gap-2">
          <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4 4m4-4v12"/></svg>
          Scheduled Backups
        </h3>
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium dark:text-gray-200">Backup otomatis</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">Simpan arsip otomatis ke folder backups/</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" id="auto-backup-toggle" aria-label="Backup otomatis" class="sr-only peer" ${enabled ? 'checked' : ''} onchange="toggleAutoBackup()">
              <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>
          <div>
            <label class="text-xs text-gray-500 dark:text-gray-400">Interval backup</label>
            <select id="backup-interval" class="w-full text-sm border dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 mt-1" onchange="changeBackupInterval()">
              <option value="1" ${interval === '1' ? 'selected' : ''}>Daily</option>
              <option value="7" ${interval === '7' ? 'selected' : ''}>Weekly</option>
              <option value="30" ${interval === '30' ? 'selected' : ''}>Monthly</option>
            </select>
          </div>
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium dark:text-gray-200">Kompres arsip (gzip)</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">Hemat ruang, restore tetap bisa baca .gz</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" id="compress-toggle" aria-label="Kompres arsip gzip" class="sr-only peer" ${compress ? 'checked' : ''} onchange="toggleCompress()">
              <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>
          <div class="flex items-center justify-between text-sm">
            <span class="text-gray-500 dark:text-gray-400">Terakhir:</span>
            <span class="font-medium dark:text-gray-200">${escapeHtml(lastRun === 'Never' ? 'Never' : new Date(lastRun).toLocaleString())}</span>
          </div>
          <button onclick="triggerBackupNow()" class="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-transform enabled:active:scale-[0.96]">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4 4m4-4v12"/></svg>
            Backup sekarang
          </button>
          <div class="flex gap-2">
            <button onclick="exportProfile()" class="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm font-medium transition">Export profil</button>
            <button onclick="cloneProfile()" class="flex-1 flex items-center justify-center gap-2 px-4 py-2 border dark:border-gray-600 dark:text-gray-200 rounded-lg text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-700 transition">Salin profil aktif</button>
          </div>
          <p class="text-xs text-gray-400 dark:text-gray-500">Arsip tersimpan di <code class="bg-gray-100 dark:bg-gray-700 px-1 rounded">backups/</code> folder aplikasi. Retensi: 7 harian + 4 mingguan + 6 bulanan.</p>
        <div class="border-t dark:border-gray-700 pt-3">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium dark:text-gray-200">Digest harian</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">Ringkasan pemasukan, pengeluaran, dan alert via channel aktif</p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" id="digest-toggle" aria-label="Digest harian" class="sr-only peer" ${digest ? 'checked' : ''} onchange="toggleDigest()">
              <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </div>
        <div class="border-t dark:border-gray-700 pt-3">
          <p class="text-sm font-medium dark:text-gray-200">Web Push (VAPID)</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">Generate sekali, simpan kedua kunci ke env server lalu restart. Private key hanya tampil sekali.</p>
          <button onclick="generateVapid()" class="px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800">Generate VAPID keys</button>
          <button onclick="rotateVapid()" class="px-4 py-2 border dark:border-gray-600 dark:text-gray-200 text-sm font-medium rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">Rotate keys</button>
          <pre id="vapid-output" class="hidden mt-2 text-xs bg-gray-100 dark:bg-gray-700 dark:text-gray-200 rounded-lg p-3 whitespace-pre-wrap break-all"></pre>
        </div>
        <div>
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs text-gray-500 dark:text-gray-400">Riwayat arsip profil ini</span>
            <button onclick="loadBackupHistory()" class="text-xs text-blue-600 hover:underline">Muat ulang</button>
          </div>
          <ul id="backup-history" class="text-xs text-gray-500 dark:text-gray-400 space-y-1"><li>Belum dimuat.</li></ul>
        </div>
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-xl border dark:border-gray-700 p-6 shadow-sm">
        <h3 class="text-sm font-semibold mb-4 dark:text-gray-200 flex items-center gap-2">
          <svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          About
        </h3>
        <div class="space-y-2 text-sm text-gray-600 dark:text-gray-300">
          <p><strong>Reign</strong> &mdash; Local-first personal finance tracker.</p>
          <p>Version 0.11.0</p>
          <p>Your data is stored locally in <code class="bg-gray-100 dark:bg-gray-700 px-1 rounded">reign.db</code>. No cloud, no accounts, no subscriptions.</p>
        </div>
      </div>
    </div>
  `;
}

async function toggleAutoBackup() {
  const enabled = document.getElementById('auto-backup-toggle').checked;
  await apiFetch('/api/settings/auto_backup_enabled', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value: enabled ? 'true' : 'false' }),
  });
}

async function toggleDigest() {
  const digest = document.getElementById('digest-toggle').checked;
  await apiFetch('/api/settings/digest_enabled', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value: digest ? 'true' : 'false' }),
  });
}

async function toggleCompress() {
  const compress = document.getElementById('compress-toggle').checked;
  await apiFetch('/api/settings/auto_backup_compress', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value: compress ? 'true' : 'false' }),
  });
}

async function changeBackupInterval() {
  const interval = document.getElementById('backup-interval').value;
  await apiFetch('/api/settings/auto_backup_interval_days', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value: interval }),
  });
}

async function rotateVapid() {
  if (!confirm('Rotate VAPID keys? Semua subscription push profil ini dihapus dan browser harus subscribe ulang.')) return;
  const el = document.getElementById('vapid-output');
  try {
    const r = await apiPost('/api/settings/vapid/rotate', {});
    const d = await r.json();
    el.classList.remove('hidden');
    el.textContent = `VAPID_PUBLIC_KEY=${d.public_key}\nVAPID_PRIVATE_KEY=${d.private_key}\n\n${d.env_hint} (${d.dropped_subscriptions} subscription dihapus). Private key hanya tampil sekali — simpan sekarang!`;
  } catch (e) {
    alert('Rotate VAPID gagal: ' + e.message);
  }
}

async function generateVapid() {
  const el = document.getElementById('vapid-output');
  try {
    const r = await apiPost('/api/settings/vapid/generate', {});
    const d = await r.json();
    el.classList.remove('hidden');
    el.textContent = `VAPID_PUBLIC_KEY=${d.public_key}\nVAPID_PRIVATE_KEY=${d.private_key}\n\n${d.env_hint} Private key hanya tampil sekali — simpan sekarang!`;
  } catch (e) {
    alert('Generate VAPID gagal: ' + e.message);
  }
}

async function loadBackupHistory() {
  const el = document.getElementById('backup-history');
  if (!el) return;
  try {
    const items = await apiGet('/api/backup/history?limit=20');
    el.innerHTML = items.length ? items.map(f => `<li>${escapeHtml(f.name)} <span class="text-gray-400">(${(f.size / 1024).toFixed(1)} KB)</span></li>`).join('') : '<li>Belum ada arsip.</li>';
  } catch {
    el.innerHTML = '<li>Gagal memuat arsip.</li>';
  }
}

async function triggerBackupNow() {
  const btn = document.activeElement;
  btn.disabled = true;
  btn.innerHTML = 'Backing up...';
  try {
    const r = await apiFetch('/api/backup/trigger', { method: 'POST' });
    const result = await r.json();
    alert(result.message);
    renderView('settings');
  } catch (e) {
    alert('Backup failed: ' + e.message);
  }
  btn.disabled = false;
  btn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4-4m0 0l-4 4m4-4v12"/></svg> Backup Now`;
}

// ============== BACKUP ==============
async function exportBackup() {
  const r = await apiFetch('/api/backup');
  if (!r.ok) { alert('Backup failed'); return; }
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `reign_backup_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
}

async function importBackup(input) {
  const file = input.files[0];
  if (!file) return;
  if (!confirm('This will REPLACE all current data. Continue?')) return;
  const form = new FormData();
  form.append('file', file);
  const r = await apiFetch('/api/restore', { method: 'POST', body: form });
  const result = await r.json();
  if (r.ok) {
    alert('Restore complete: ' + result.message);
    navigate('dashboard');
  } else {
    alert('Restore failed: ' + (result.detail || 'Unknown error'));
  }
}

async function exportProfile() {
  const r = await apiFetch('/api/profiles/export');
  if (!r.ok) { alert('Export profil gagal'); return; }
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `reign_profile_${activeProfile}_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
}

async function cloneProfile() {
  const target = prompt('Salin profil aktif sebagai profil baru bernama:');
  if (!target) return;
  const r = await apiFetch('/api/backup/profiles/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug: target }),
  });
  const result = await r.json().catch(() => ({}));
  if (r.ok) {
    alert('Profil disalin: ' + result.to);
    await refreshProfileSelect();
    renderView('settings');
  } else {
    alert('Salin profil gagal: ' + (result.detail || 'Unknown error'));
  }
}

// Init
document.getElementById('current-date').textContent = new Date().toLocaleDateString('en-US', {
  weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
});
refreshProfileSelect();
navigate('dashboard');

// ============== PROFILES ==============
async function refreshProfileSelect() {
  const sel = document.getElementById('profile-select');
  if (!sel) return;
  let profiles = ['default'];
  try {
    profiles = await apiGet('/api/profiles');
  } catch { /* offline: keep default */ }
  if (!profiles.includes(activeProfile)) profiles.push(activeProfile);
  sel.innerHTML = profiles.map(p => `<option value="${escapeHtml(p)}" ${p === activeProfile ? 'selected' : ''}>${escapeHtml(p)}</option>`).join('');
}

async function switchProfile(slug) {
  const name = (slug || 'default').trim().toLowerCase();
  if (!name) return;
  if (name !== 'default') {
    const r = await fetch(API + '/api/profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: name }),
    });
    if (!r.ok) { alert('Profil tidak valid'); refreshProfileSelect(); return; }
  }
  activeProfile = name;
  localStorage.setItem('reign_profile', name);
  refreshProfileSelect();
  renderView(currentView);
}

// PWA: register service worker (offline shell). No-op when unsupported.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}
