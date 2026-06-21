let screens = [];
let products = [];

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function esc(value) {
  return String(value ?? '').replace(/[&<>"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char]));
}

function selectedProductIds() {
  return [...document.querySelectorAll('input[name="kitchen-product"]:checked')].map(input => Number(input.value));
}

async function loadAll() {
  [screens, products] = await Promise.all([
    api('/api/kitchen-screens/admin'),
    api('/api/products/admin'),
  ]);
  renderProductChecks();
  renderScreens();
}

function renderProductChecks(selected = []) {
  const selectedSet = new Set(selected.map(Number));
  document.querySelector('#product-checkboxes').innerHTML = products.map(product => `
    <label>
      <input type="checkbox" name="kitchen-product" value="${product.id}" ${selectedSet.has(product.id) ? 'checked' : ''}>
      <span>${esc(product.name_short || product.name)}</span>
      <small>${esc(product.category_name)}</small>
    </label>
  `).join('');
}

function renderScreens() {
  document.querySelector('#screens-table tbody').innerHTML = screens.map(screen => `
    <tr class="${screen.is_active ? '' : 'inactive-row'}">
      <td>${screen.sort_order}</td>
      <td>${esc(screen.name)}</td>
      <td><code>${esc(screen.slug)}</code></td>
      <td>${screen.product_names.map(esc).join(', ') || '—'}</td>
      <td>${screen.is_active ? 'sì' : 'no'}</td>
      <td><a href="/kitchen/${encodeURIComponent(screen.slug)}">apri</a></td>
      <td><button data-edit-id="${screen.id}">Modifica</button></td>
    </tr>
  `).join('');
}

function resetForm() {
  document.querySelector('#editor-title').textContent = 'Nuova schermata';
  document.querySelector('#screen-id').value = '';
  document.querySelector('#screen-name').value = '';
  document.querySelector('#screen-slug').value = '';
  document.querySelector('#screen-sort').value = '0';
  document.querySelector('#screen-active').checked = true;
  document.querySelector('#delete-screen').hidden = true;
  renderProductChecks();
  document.querySelector('#settings-status').textContent = '';
}

function editScreen(id) {
  const screen = screens.find(item => item.id === id);
  if (!screen) return;
  document.querySelector('#editor-title').textContent = `Modifica: ${screen.name}`;
  document.querySelector('#screen-id').value = screen.id;
  document.querySelector('#screen-name').value = screen.name;
  document.querySelector('#screen-slug').value = screen.slug;
  document.querySelector('#screen-sort').value = screen.sort_order ?? 0;
  document.querySelector('#screen-active').checked = Boolean(screen.is_active);
  document.querySelector('#delete-screen').hidden = false;
  renderProductChecks(screen.product_ids);
  document.querySelector('#settings-status').textContent = '';
}

function payloadFromForm() {
  return {
    name: document.querySelector('#screen-name').value.trim(),
    slug: document.querySelector('#screen-slug').value.trim(),
    sort_order: Number(document.querySelector('#screen-sort').value || 0),
    is_active: document.querySelector('#screen-active').checked,
    product_ids: selectedProductIds(),
  };
}

document.addEventListener('click', event => {
  const editButton = event.target.closest('[data-edit-id]');
  if (editButton) editScreen(Number(editButton.dataset.editId));
});

document.querySelector('#new-screen').addEventListener('click', resetForm);
document.querySelector('#reset-form').addEventListener('click', resetForm);

document.querySelector('#screen-form').addEventListener('submit', async event => {
  event.preventDefault();
  const status = document.querySelector('#settings-status');
  const id = document.querySelector('#screen-id').value;
  const payload = payloadFromForm();
  status.textContent = 'Salvataggio...';
  try {
    if (id) {
      await api(`/api/kitchen-screens/${id}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    } else {
      await api('/api/kitchen-screens', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    }
    status.textContent = 'Salvato.';
    await loadAll();
    if (!id) resetForm();
  } catch (error) {
    status.textContent = `Errore: ${error.message}`;
  }
});

document.querySelector('#delete-screen').addEventListener('click', async () => {
  const id = document.querySelector('#screen-id').value;
  if (!id || !confirm('Eliminare questa schermata cucina?')) return;
  const status = document.querySelector('#settings-status');
  status.textContent = 'Eliminazione...';
  try {
    await api(`/api/kitchen-screens/${id}`, {method: 'DELETE'});
    status.textContent = 'Eliminata.';
    await loadAll();
    resetForm();
  } catch (error) {
    status.textContent = `Errore: ${error.message}`;
  }
});

loadAll().then(resetForm);
