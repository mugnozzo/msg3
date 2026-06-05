const tableBody = document.querySelector('#cashiers-table tbody');
const form = document.querySelector('#cashier-form');
const formTitle = document.querySelector('#form-title');
const newButton = document.querySelector('#new-cashier');
const resetButton = document.querySelector('#reset-form');

let cashiers = [];
let menus = [];
let printers = [];

function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'}[char]));
}

async function loadAll() {
  const [cashiersRes, menusRes, printersRes] = await Promise.all([
    fetch('/api/cashiers'),
    fetch('/api/meta/menus'),
    fetch('/api/printers')
  ]);
  if (!cashiersRes.ok) throw new Error(await cashiersRes.text());
  if (!menusRes.ok) throw new Error(await menusRes.text());
  if (!printersRes.ok) throw new Error(await printersRes.text());

  cashiers = await cashiersRes.json();
  menus = await menusRes.json();
  printers = await printersRes.json();
  renderSelects();
  renderCashiers();
}

function renderSelects() {
  form.elements.menu_id.innerHTML = menus.map(menu =>
    `<option value="${menu.id}">${escapeHtml(menu.name)} (${escapeHtml(menu.slug)})</option>`
  ).join('');

  form.elements.printer_id.innerHTML = printers.map(printer =>
    `<option value="${printer.id}">${escapeHtml(printer.name)}${printer.enabled ? '' : ' — disattivata'}</option>`
  ).join('');
}

function renderCashiers() {
  tableBody.innerHTML = cashiers.map(cashier => `
    <tr class="${cashier.enabled ? '' : 'inactive-row'}">
      <td>${cashier.id}</td>
      <td>${escapeHtml(cashier.name)}</td>
      <td>${escapeHtml(cashier.menu_name ?? '—')}</td>
      <td>${escapeHtml(cashier.printer_name ?? '—')}</td>
      <td>${cashier.enabled ? 'Attiva' : 'Disattivata'}</td>
      <td><a href="/cashier/${cashier.id}">/cashier/${cashier.id}</a></td>
      <td class="row-actions">
        <button data-action="edit" data-id="${cashier.id}">Modifica</button>
        <button data-action="delete" data-id="${cashier.id}">Elimina</button>
      </td>
    </tr>
  `).join('');
}

function resetForm() {
  form.reset();
  form.elements.id.value = '';
  form.elements.enabled.checked = true;
  formTitle.textContent = 'Nuova cassa';
}

function editCashier(id) {
  const cashier = cashiers.find(item => item.id === Number(id));
  if (!cashier) return;
  form.elements.id.value = cashier.id;
  form.elements.name.value = cashier.name;
  form.elements.menu_id.value = cashier.menu_id;
  form.elements.printer_id.value = cashier.printer_id;
  form.elements.enabled.checked = Boolean(cashier.enabled);
  formTitle.textContent = `Modifica: ${cashier.name}`;
}

async function saveCashier(event) {
  event.preventDefault();
  const id = form.elements.id.value;
  const payload = {
    name: form.elements.name.value.trim(),
    menu_id: Number(form.elements.menu_id.value),
    printer_id: Number(form.elements.printer_id.value),
    enabled: form.elements.enabled.checked
  };
  const res = await fetch(id ? `/api/cashiers/${id}` : '/api/cashiers', {
    method: id ? 'PUT' : 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  resetForm();
  await loadAll();
}

async function deleteCashier(id) {
  if (!confirm('Eliminare questa cassa? Se ha già ordini, verrà solo disattivata.')) return;
  const res = await fetch(`/api/cashiers/${id}`, {method: 'DELETE'});
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  const result = await res.json();
  if (result.status === 'disabled') alert(result.reason);
  await loadAll();
}

tableBody.addEventListener('click', event => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const {action, id} = button.dataset;
  if (action === 'edit') editCashier(id);
  if (action === 'delete') deleteCashier(id);
});

form.addEventListener('submit', saveCashier);
resetButton.addEventListener('click', resetForm);
newButton.addEventListener('click', resetForm);

loadAll().catch(error => alert(error.message));
