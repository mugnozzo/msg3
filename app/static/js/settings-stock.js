const stockDateInput = document.querySelector('#stock-date');
const stockStatus = document.querySelector('#stock-status');
const stockForm = document.querySelector('#stock-item-form');
const stockFormTitle = document.querySelector('#stock-form-title');
const stockIdInput = document.querySelector('#stock-item-id');
const stockSlugInput = document.querySelector('#stock-slug');
const stockNameInput = document.querySelector('#stock-name');
const stockUnitInput = document.querySelector('#stock-unit-name');
const stockSortInput = document.querySelector('#stock-sort-order');
const stockEnabledInput = document.querySelector('#stock-enabled');
const resetStockFormButton = document.querySelector('#reset-stock-form');
const usageSection = document.querySelector('#stock-usage-section');
const usageTitle = document.querySelector('#stock-usage-title');
const usageRows = document.querySelector('#stock-usage-rows');
const saveUsagesButton = document.querySelector('#save-stock-usages');

let stockItems = [];
let allStockItems = [];
let products = [];
let selectedStockItemId = null;

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function statusLabel(status) {
  if (status === 'insufficient') return 'Stock insufficiente';
  if (status === 'low') return 'In esaurimento';
  if (status === 'untracked') return 'Non monitorato';
  return 'Ok';
}

function inputValue(item, field) {
  const value = item[field];
  return value === null || value === undefined ? '' : String(value).replace('.', ',');
}

function setStatus(message) {
  stockStatus.textContent = message || '';
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await response.text());
  return response.status === 204 ? null : response.json();
}

async function loadProducts() {
  products = await fetchJson('/api/products/admin');
}

async function loadStockItems() {
  allStockItems = await fetchJson('/api/stock/items?include_disabled=true');
  renderStockDefinitions();
}

async function loadStock() {
  const dateParam = stockDateInput.value ? `?business_date=${encodeURIComponent(stockDateInput.value)}` : '';
  const data = await fetchJson(`/api/stock/status${dateParam}`);
  stockDateInput.value = data.business_date;
  stockItems = data.items;
  renderStock();
}

function renderStock() {
  const tbody = document.querySelector('#stock-table tbody');
  tbody.innerHTML = stockItems.map(item => `
    <tr data-stock-item-id="${item.id}">
      <td><strong>${escapeHtml(item.name)}</strong><br><small>${escapeHtml(item.slug)}</small></td>
      <td>${escapeHtml(item.unit_name)}</td>
      <td><input class="stock-initial" inputmode="decimal" value="${escapeHtml(inputValue(item, 'initial_quantity'))}" placeholder="vuoto = non monitorato"></td>
      <td><input class="stock-threshold" inputmode="decimal" value="${escapeHtml(inputValue(item, 'warning_threshold'))}" placeholder="es. 10"></td>
      <td>${escapeHtml(item.consumed_display)}</td>
      <td><strong>${escapeHtml(item.remaining_display)}</strong></td>
      <td><span class="stock-status stock-status-${escapeHtml(item.status)}">${statusLabel(item.status)}</span></td>
      <td><button type="button" data-save-stock="${item.id}">Salva</button></td>
    </tr>
  `).join('') || '<tr><td colspan="8">Nessuno stock attivo.</td></tr>';
}

function renderStockDefinitions() {
  const tbody = document.querySelector('#stock-items-table tbody');
  tbody.innerHTML = allStockItems.map(item => `
    <tr data-definition-id="${item.id}">
      <td><strong>${escapeHtml(item.name)}</strong><br><small>${escapeHtml(item.slug)}</small></td>
      <td>${escapeHtml(item.unit_name)}</td>
      <td>${Number(item.enabled) ? 'Sì' : 'No'}</td>
      <td>${escapeHtml(item.sort_order)}</td>
      <td>${escapeHtml(item.usage_count || 0)}</td>
      <td>${escapeHtml(item.configured_days || 0)}</td>
      <td class="actions-cell">
        <button type="button" data-edit-stock-item="${item.id}">Modifica</button>
        <button type="button" data-edit-usages="${item.id}">Consumi</button>
        <button type="button" data-toggle-stock-item="${item.id}" data-enabled="${Number(item.enabled) ? '0' : '1'}">${Number(item.enabled) ? 'Disattiva' : 'Attiva'}</button>
        <button type="button" data-delete-stock-item="${item.id}">Elimina</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="7">Nessuno stock definito.</td></tr>';
}

function resetStockForm() {
  stockFormTitle.textContent = 'Crea nuovo stock';
  stockIdInput.value = '';
  stockSlugInput.value = '';
  stockNameInput.value = '';
  stockUnitInput.value = '';
  stockSortInput.value = '0';
  stockEnabledInput.checked = true;
}

function editStockItem(stockItemId) {
  const item = allStockItems.find(current => Number(current.id) === Number(stockItemId));
  if (!item) return;
  stockFormTitle.textContent = `Modifica: ${item.name}`;
  stockIdInput.value = item.id;
  stockSlugInput.value = item.slug;
  stockNameInput.value = item.name;
  stockUnitInput.value = item.unit_name;
  stockSortInput.value = item.sort_order || 0;
  stockEnabledInput.checked = Boolean(Number(item.enabled));
}

async function saveStockItem(event) {
  event.preventDefault();
  const stockItemId = stockIdInput.value;
  const payload = {
    slug: stockSlugInput.value.trim(),
    name: stockNameInput.value.trim(),
    unit_name: stockUnitInput.value.trim() || 'unità',
    sort_order: Number(stockSortInput.value || 0),
    enabled: stockEnabledInput.checked,
  };
  const url = stockItemId ? `/api/stock/items/${stockItemId}` : '/api/stock/items';
  const method = stockItemId ? 'PUT' : 'POST';
  await fetchJson(url, {
    method,
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  setStatus('Definizione stock salvata.');
  resetStockForm();
  await Promise.all([loadStockItems(), loadStock()]);
}

async function toggleStockItem(stockItemId, enabled) {
  await fetchJson(`/api/stock/items/${stockItemId}/enabled?enabled=${enabled ? 'true' : 'false'}`, {method: 'PATCH'});
  setStatus(enabled ? 'Stock attivato.' : 'Stock disattivato.');
  await Promise.all([loadStockItems(), loadStock()]);
}

async function deleteStockItem(stockItemId) {
  const item = allStockItems.find(current => Number(current.id) === Number(stockItemId));
  const ok = window.confirm(`Eliminare lo stock "${item ? item.name : stockItemId}"?\n\nNota: gli stock con storico o associazioni prodotto non vengono eliminati; vanno disattivati.`);
  if (!ok) return;
  await fetchJson(`/api/stock/items/${stockItemId}`, {method: 'DELETE'});
  setStatus('Stock eliminato.');
  await Promise.all([loadStockItems(), loadStock()]);
}

async function saveStock(stockItemId) {
  const row = document.querySelector(`tr[data-stock-item-id="${stockItemId}"]`);
  const payload = {
    business_date: stockDateInput.value,
    initial_quantity: row.querySelector('.stock-initial').value.trim() || null,
    warning_threshold: row.querySelector('.stock-threshold').value.trim() || null,
  };
  await fetchJson(`/api/stock/items/${stockItemId}/day`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  setStatus('Stock serata salvato.');
  await loadStock();
}

async function editUsages(stockItemId) {
  selectedStockItemId = Number(stockItemId);
  const item = allStockItems.find(current => Number(current.id) === selectedStockItemId);
  usageTitle.textContent = item ? `Consumi prodotto → ${item.name}` : 'Consumi prodotto';
  const usages = await fetchJson(`/api/stock/items/${selectedStockItemId}/usages`);
  const usageByProductId = new Map(usages.map(usage => [Number(usage.product_id), usage.quantity_display]));
  usageRows.innerHTML = products.map(product => {
    const value = usageByProductId.get(Number(product.id)) || '';
    return `
      <tr>
        <td><strong>${escapeHtml(product.name)}</strong><br><small>${escapeHtml(product.slug)} · ${escapeHtml(product.category_name || '')}</small></td>
        <td><input class="usage-quantity" data-product-id="${product.id}" inputmode="decimal" value="${escapeHtml(value)}" placeholder="vuoto = non consuma"></td>
      </tr>
    `;
  }).join('');
  usageSection.hidden = false;
}

async function saveUsages() {
  if (!selectedStockItemId) return;
  const usages = Array.from(document.querySelectorAll('.usage-quantity'))
    .map(input => ({product_id: Number(input.dataset.productId), quantity: input.value.trim()}))
    .filter(usage => usage.quantity !== '');
  await fetchJson(`/api/stock/items/${selectedStockItemId}/usages`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({usages}),
  });
  setStatus('Associazioni prodotto-stock salvate.');
  await Promise.all([loadStockItems(), loadStock()]);
}

document.addEventListener('click', event => {
  const saveNightButton = event.target.closest('[data-save-stock]');
  if (saveNightButton) {
    saveStock(Number(saveNightButton.dataset.saveStock)).catch(error => setStatus(`Errore: ${error.message}`));
    return;
  }

  const editButton = event.target.closest('[data-edit-stock-item]');
  if (editButton) {
    editStockItem(Number(editButton.dataset.editStockItem));
    return;
  }

  const toggleButton = event.target.closest('[data-toggle-stock-item]');
  if (toggleButton) {
    toggleStockItem(Number(toggleButton.dataset.toggleStockItem), toggleButton.dataset.enabled === '1')
      .catch(error => setStatus(`Errore: ${error.message}`));
    return;
  }

  const deleteButton = event.target.closest('[data-delete-stock-item]');
  if (deleteButton) {
    deleteStockItem(Number(deleteButton.dataset.deleteStockItem)).catch(error => setStatus(`Errore: ${error.message}`));
    return;
  }

  const usageButton = event.target.closest('[data-edit-usages]');
  if (usageButton) {
    editUsages(Number(usageButton.dataset.editUsages)).catch(error => setStatus(`Errore: ${error.message}`));
  }
});

stockForm.addEventListener('submit', event => {
  saveStockItem(event).catch(error => setStatus(`Errore: ${error.message}`));
});

resetStockFormButton.addEventListener('click', resetStockForm);
saveUsagesButton.addEventListener('click', () => saveUsages().catch(error => setStatus(`Errore: ${error.message}`)));

stockDateInput.addEventListener('change', () => {
  loadStock().catch(error => setStatus(`Errore: ${error.message}`));
});

Promise.all([loadProducts(), loadStockItems(), loadStock()]).catch(error => setStatus(`Errore: ${error.message}`));
