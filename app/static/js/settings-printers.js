const tableBody = document.querySelector('#printers-table tbody');
const form = document.querySelector('#printer-form');
const formTitle = document.querySelector('#form-title');
const newButton = document.querySelector('#new-printer');
const resetButton = document.querySelector('#reset-form');
const hint = document.querySelector('#address-hint');

let printers = [];

function kindLabel(kind) {
  return {
    file: 'File di test',
    usb: 'USB',
    network: 'Ethernet'
  }[kind] || kind;
}

function updateHint() {
  const kind = form.elements.kind.value;
  const hints = {
    file: 'Per test sicuri. Lascia vuoto per usare data/printer-output.bin.',
    usb: 'Esempio: /dev/usb/lp0 oppure /dev/lp0. Il processo deve avere permessi di scrittura.',
    network: 'Esempio: 192.168.1.50:9100. La porta ESC/POS più comune è 9100.'
  };
  const placeholders = {
    file: 'data/printer-output.bin',
    usb: '/dev/usb/lp0',
    network: '192.168.1.50:9100'
  };
  hint.textContent = hints[kind];
  form.elements.address.placeholder = placeholders[kind];
}

function moneySafe(text) {
  return String(text ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;'}[char]));
}

async function loadPrinters() {
  const res = await fetch('/api/printers');
  if (!res.ok) throw new Error(await res.text());
  printers = await res.json();
  renderPrinters();
}

function renderPrinters() {
  tableBody.innerHTML = printers.map(printer => `
    <tr class="${printer.enabled ? '' : 'inactive-row'}">
      <td>${moneySafe(printer.name)}</td>
      <td>${kindLabel(printer.kind)}</td>
      <td><code>${moneySafe(printer.address)}</code></td>
      <td>${printer.cut_enabled ? 'Attivo' : 'Disattivato'}</td>
      <td>${printer.enabled ? 'Attiva' : 'Disattivata'}</td>
      <td class="row-actions">
        <button data-action="test" data-id="${printer.id}">Test</button>
        <button data-action="edit" data-id="${printer.id}">Modifica</button>
        <button data-action="delete" data-id="${printer.id}">Elimina</button>
      </td>
    </tr>
  `).join('');
}

function resetForm() {
  form.reset();
  form.elements.id.value = '';
  form.elements.enabled.checked = true;
  form.elements.cut_enabled.checked = true;
  formTitle.textContent = 'Nuova stampante';
  updateHint();
}

function editPrinter(id) {
  const printer = printers.find(item => item.id === Number(id));
  if (!printer) return;
  form.elements.id.value = printer.id;
  form.elements.name.value = printer.name;
  form.elements.kind.value = printer.kind;
  form.elements.address.value = printer.address;
  form.elements.enabled.checked = Boolean(printer.enabled);
  form.elements.cut_enabled.checked = Boolean(printer.cut_enabled);
  formTitle.textContent = `Modifica: ${printer.name}`;
  updateHint();
}

async function savePrinter(event) {
  event.preventDefault();
  const id = form.elements.id.value;
  const payload = {
    name: form.elements.name.value.trim(),
    kind: form.elements.kind.value,
    address: form.elements.address.value.trim(),
    enabled: form.elements.enabled.checked,
    cut_enabled: form.elements.cut_enabled.checked
  };
  const res = await fetch(id ? `/api/printers/${id}` : '/api/printers', {
    method: id ? 'PUT' : 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  resetForm();
  await loadPrinters();
}

async function testPrinter(id, button) {
  button.disabled = true;
  const oldText = button.textContent;
  button.textContent = 'Test...';
  try {
    const res = await fetch(`/api/printers/${id}/test`, {method: 'POST'});
    if (!res.ok) throw new Error(await res.text());
    button.textContent = 'OK';
    setTimeout(() => { button.textContent = oldText; button.disabled = false; }, 1200);
  } catch (error) {
    alert(error.message);
    button.textContent = oldText;
    button.disabled = false;
  }
}

async function deletePrinter(id) {
  if (!confirm('Eliminare questa stampante? Se è già usata, verrà solo disattivata.')) return;
  const res = await fetch(`/api/printers/${id}`, {method: 'DELETE'});
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  const result = await res.json();
  if (result.status === 'disabled') alert(result.reason);
  await loadPrinters();
}

tableBody.addEventListener('click', event => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const {action, id} = button.dataset;
  if (action === 'edit') editPrinter(id);
  if (action === 'test') testPrinter(id, button);
  if (action === 'delete') deletePrinter(id);
});

form.addEventListener('submit', savePrinter);
form.elements.kind.addEventListener('change', updateHint);
resetButton.addEventListener('click', resetForm);
newButton.addEventListener('click', resetForm);

resetForm();
loadPrinters().catch(error => alert(error.message));
