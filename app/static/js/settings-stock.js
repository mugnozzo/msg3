const stockDateInput = document.querySelector('#stock-date');
const stockStatus = document.querySelector('#stock-status');
let stockItems = [];

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

async function loadStock() {
  const dateParam = stockDateInput.value ? `?business_date=${encodeURIComponent(stockDateInput.value)}` : '';
  const response = await fetch(`/api/stock/status${dateParam}`);
  if (!response.ok) throw new Error(await response.text());
  const data = await response.json();
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
  `).join('') || '<tr><td colspan="8">Nessuno stock configurato.</td></tr>';
}

async function saveStock(stockItemId) {
  const row = document.querySelector(`tr[data-stock-item-id="${stockItemId}"]`);
  const payload = {
    business_date: stockDateInput.value,
    initial_quantity: row.querySelector('.stock-initial').value.trim() || null,
    warning_threshold: row.querySelector('.stock-threshold').value.trim() || null,
  };
  const response = await fetch(`/api/stock/items/${stockItemId}/day`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  stockStatus.textContent = 'Stock salvato.';
  await loadStock();
}

document.addEventListener('click', event => {
  const button = event.target.closest('[data-save-stock]');
  if (!button) return;
  saveStock(Number(button.dataset.saveStock)).catch(error => {
    stockStatus.textContent = `Errore: ${error.message}`;
  });
});

stockDateInput.addEventListener('change', () => {
  loadStock().catch(error => stockStatus.textContent = `Errore: ${error.message}`);
});

loadStock().catch(error => stockStatus.textContent = `Errore: ${error.message}`);
