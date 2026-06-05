let products = [];
let categories = [];
let menus = [];

const money = cents => `€ ${(cents / 100).toFixed(2).replace('.', ',')}`;
const centsToInput = cents => (cents / 100).toFixed(2).replace('.', ',');
const inputToCents = value => Math.round((Number.parseFloat(String(value).replace(',', '.')) || 0) * 100);

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

async function loadAll() {
  [products, categories, menus] = await Promise.all([
    api('/api/products/admin'),
    api('/api/meta/categories'),
    api('/api/meta/menus'),
  ]);
  renderCategoryOptions();
  renderMenuChecks();
  renderProducts();
}

function renderCategoryOptions() {
  document.querySelector('#product-category').innerHTML = categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

function renderMenuChecks(selected = []) {
  const selectedSet = new Set(selected.map(Number));
  document.querySelector('#menu-checkboxes').innerHTML = menus.map(m => `
    <label><input type="checkbox" name="menu" value="${m.id}" ${selectedSet.has(m.id) ? 'checked' : ''}> ${m.name}</label>
  `).join('');
}

function renderProducts() {
  document.querySelector('#products-table tbody').innerHTML = products.map(p => `
    <tr class="${p.enabled ? '' : 'inactive-row'}">
      <td>${p.sort_order}</td>
      <td>${p.icon ?? ''}</td>
      <td>${p.name}</td>
      <td>${p.category_name}</td>
      <td>${money(p.price_cents)}</td>
      <td>${p.menu_names.join(', ')}</td>
      <td>${p.enabled ? 'sì' : 'no'}</td>
      <td><button data-edit-id="${p.id}">Modifica</button></td>
    </tr>
  `).join('');
}

function resetForm() {
  document.querySelector('#editor-title').textContent = 'Nuovo prodotto';
  document.querySelector('#product-id').value = '';
  document.querySelector('#product-name').value = '';
  document.querySelector('#product-price').value = '';
  document.querySelector('#product-icon').value = '';
  document.querySelector('#product-image').value = '';
  document.querySelector('#product-sort').value = '0';
  document.querySelector('#product-enabled').checked = true;
  if (categories[0]) document.querySelector('#product-category').value = categories[0].id;
  renderMenuChecks(menus.length ? [menus[0].id] : []);
  document.querySelector('#settings-status').textContent = '';
}

function editProduct(id) {
  const product = products.find(p => p.id === id);
  if (!product) return;
  document.querySelector('#editor-title').textContent = `Modifica: ${product.name}`;
  document.querySelector('#product-id').value = product.id;
  document.querySelector('#product-name').value = product.name;
  document.querySelector('#product-price').value = centsToInput(product.price_cents);
  document.querySelector('#product-category').value = product.category_id;
  document.querySelector('#product-icon').value = product.icon ?? '';
  document.querySelector('#product-image').value = product.image_path ?? '';
  document.querySelector('#product-sort').value = product.sort_order ?? 0;
  document.querySelector('#product-enabled').checked = Boolean(product.enabled);
  renderMenuChecks(product.menu_ids);
  document.querySelector('#settings-status').textContent = '';
}

function payloadFromForm() {
  return {
    name: document.querySelector('#product-name').value.trim(),
    price_cents: inputToCents(document.querySelector('#product-price').value),
    category_id: Number(document.querySelector('#product-category').value),
    enabled: document.querySelector('#product-enabled').checked,
    icon: document.querySelector('#product-icon').value.trim() || null,
    image_path: document.querySelector('#product-image').value.trim() || null,
    sort_order: Number(document.querySelector('#product-sort').value || 0),
    menu_ids: [...document.querySelectorAll('input[name="menu"]:checked')].map(input => Number(input.value)),
  };
}

document.addEventListener('click', event => {
  const editButton = event.target.closest('[data-edit-id]');
  if (editButton) editProduct(Number(editButton.dataset.editId));
});

document.querySelector('#new-product').addEventListener('click', resetForm);
document.querySelector('#reset-form').addEventListener('click', resetForm);

document.querySelector('#product-form').addEventListener('submit', async event => {
  event.preventDefault();
  const status = document.querySelector('#settings-status');
  const id = document.querySelector('#product-id').value;
  const payload = payloadFromForm();
  status.textContent = 'Salvataggio...';
  try {
    if (id) {
      await api(`/api/products/${id}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    } else {
      await api('/api/products', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    }
    status.textContent = 'Salvato.';
    await loadAll();
    if (!id) resetForm();
  } catch (error) {
    status.textContent = `Errore: ${error.message}`;
  }
});

loadAll().then(resetForm);
