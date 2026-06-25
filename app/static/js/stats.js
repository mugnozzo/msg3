const money = cents => `€ ${((Number(cents) || 0) / 100).toFixed(2).replace('.', ',')}`;
const n = value => String(Number(value) || 0);
const statusEl = document.querySelector('#stats-status');
const form = document.querySelector('#stats-filters');
const endInput = document.querySelector('#end');
const endNow = document.querySelector('#end-now');
let allProducts = [];

function localDateTimeValue(date) {
  const pad = value => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function setStatus(message) {
  statusEl.textContent = message || '';
}

function option(value, label) {
  return `<option value="${value}">${label}</option>`;
}

async function loadFilterOptions() {
  const res = await fetch('/api/stats/filters');
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  allProducts = data.products || [];

  document.querySelector('#category-filter').innerHTML = '<option value="">Tutte</option>' +
    data.categories.map(item => option(item.id, item.name)).join('');
  document.querySelector('#cashier-filter').innerHTML = '<option value="">Tutte</option>' +
    data.cashiers.map(item => option(item.id, item.name)).join('');
  document.querySelector('#menu-filter').innerHTML = '<option value="">Tutti</option>' +
    data.menus.map(item => option(item.id, item.name)).join('');
  refreshProductOptions();
}

function refreshProductOptions() {
  const categoryId = document.querySelector('#category-filter').value;
  const products = categoryId ? allProducts.filter(p => String(p.category_id) === String(categoryId)) : allProducts;
  document.querySelector('#product-filter').innerHTML = '<option value="">Tutti</option>' +
    products.map(item => option(item.id, `${item.name} (${item.slug})`)).join('');
}

function buildQuery() {
  const params = new URLSearchParams();
  const data = new FormData(form);
  for (const [key, value] of data.entries()) {
    if (value) params.set(key, value);
  }
  params.delete('end');
  if (endNow.checked) {
    params.set('end', 'now');
  } else if (endInput.value) {
    params.set('end', endInput.value);
  }
  return params.toString();
}

function renderSummary(data) {
  const summary = data.summary || {};
  document.querySelector('#summary-total').textContent = money(summary.total_cents);
  document.querySelector('#summary-orders').textContent = n(summary.order_count);
  document.querySelector('#summary-items').textContent = n(summary.item_count);
  const start = data.filters?.start_display || 'inizio';
  const end = data.filters?.end === 'now' ? 'adesso' : (data.filters?.end_display || 'fine');
  document.querySelector('#summary-range').textContent = `${start} → ${end}`;
}

function renderGroups(data) {
  const groups = data.groups || [];
  document.querySelector('#groups-section').hidden = data.filters?.group_by === 'none';
  document.querySelector('#groups-table tbody').innerHTML = groups.length ? groups.map(row => `
    <tr>
      <td>${row.label || '—'}</td>
      <td>${n(row.order_count)}</td>
      <td>${n(row.item_count)}</td>
      <td>${money(row.total_cents)}</td>
    </tr>
  `).join('') : '<tr><td colspan="4">Nessun dato.</td></tr>';
}

function renderProducts(data) {
  const products = data.products || [];
  document.querySelector('#products-table tbody').innerHTML = products.length ? products.map(row => `
    <tr>
      <td>${row.category_name || ''}</td>
      <td>${row.product_name || ''}</td>
      <td><code>${row.slug || ''}</code></td>
      <td>${n(row.quantity)}</td>
      <td>${money(row.avg_price_cents)}</td>
      <td>${money(row.total_cents)}</td>
    </tr>
  `).join('') : '<tr><td colspan="6">Nessun prodotto trovato.</td></tr>';
}

async function loadStats() {
  setStatus('Caricamento...');
  const res = await fetch(`/api/stats?${buildQuery()}`);
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  renderSummary(data);
  renderGroups(data);
  renderProducts(data);
  setStatus('Aggiornato.');
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  try { await loadStats(); } catch (err) { setStatus('Errore.'); alert(err.message); }
});

document.querySelector('#category-filter').addEventListener('change', () => {
  refreshProductOptions();
});

endNow.addEventListener('change', () => {
  endInput.disabled = endNow.checked;
});

document.querySelector('#today-button').addEventListener('click', async () => {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
  document.querySelector('#start').value = localDateTimeValue(start);
  endNow.checked = true;
  endInput.disabled = true;
  await loadStats();
});

document.querySelector('#clear-button').addEventListener('click', async () => {
  form.reset();
  endNow.checked = true;
  endInput.disabled = true;
  refreshProductOptions();
  await loadStats();
});

(async function init() {
  try {
    await loadFilterOptions();
    endInput.disabled = true;
    await loadStats();
  } catch (err) {
    setStatus('Errore.');
    alert(err.message);
  }
})();
