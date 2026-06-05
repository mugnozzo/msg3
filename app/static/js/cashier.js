const menu = document.querySelector('.cashier').dataset.menu;
const cart = new Map();
let products = [];

const money = cents => `€ ${(cents / 100).toFixed(2).replace('.', ',')}`;

async function loadProducts() {
  const response = await fetch(`/api/products?menu=${encodeURIComponent(menu)}`);
  products = await response.json();
  renderProducts();
}

function renderProducts() {
  const grid = document.querySelector('#product-grid');
  grid.innerHTML = products.map(product => `
    <button class="product-button" data-product-id="${product.id}">
      <span class="icon">${product.icon ?? '□'}</span>
      <strong class="name">${product.name}</strong>
      <span class="price">${money(product.price_cents)}</span>
    </button>
  `).join('');
}

function addProduct(productId) {
  const product = products.find(item => item.id === productId);
  if (!product) return;
  const current = cart.get(productId) ?? { product, quantity: 0 };
  current.quantity += 1;
  cart.set(productId, current);
  renderCart();
}

function decrementProduct(productId) {
  const current = cart.get(productId);
  if (!current) return;
  current.quantity -= 1;
  if (current.quantity <= 0) cart.delete(productId);
  renderCart();
}

function getTotalCents() {
  return [...cart.values()].reduce((sum, item) => sum + item.product.price_cents * item.quantity, 0);
}

function quickPaidValues(totalCents) {
  if (totalCents <= 0) return [];
  const euros = Math.ceil(totalCents / 100);
  const candidates = new Set([euros]);
  for (const step of [5, 10, 20, 50, 100]) {
    candidates.add(Math.ceil(euros / step) * step);
  }
  return [...candidates].filter(v => v > 0).sort((a, b) => a - b).slice(0, 5);
}

function renderCart() {
  const lines = document.querySelector('#cart-lines');
  lines.innerHTML = [...cart.values()].map(item => `
    <div class="cart-line">
      <span>${item.quantity}× ${item.product.name}</span>
      <strong>${money(item.product.price_cents * item.quantity)}</strong>
      <button data-remove-id="${item.product.id}">−</button>
    </div>
  `).join('') || '<p>Nessun prodotto selezionato.</p>';

  const total = getTotalCents();
  document.querySelector('#cart-total').textContent = money(total);
  document.querySelector('#quick-paid').innerHTML = quickPaidValues(total).map(v => `<button data-paid="${v}">€ ${v}</button>`).join('');
  updateChange();
}

function updateChange() {
  const paidRaw = document.querySelector('#paid-input').value.replace(',', '.');
  const paidCents = Math.round((Number.parseFloat(paidRaw) || 0) * 100);
  const change = Math.max(0, paidCents - getTotalCents());
  document.querySelector('#change-output').textContent = money(change);
}

async function printOrder() {
  const button = document.querySelector('#print-order');
  const status = document.querySelector('#status');
  if (cart.size === 0) return;
  button.disabled = true;
  status.textContent = 'Stampa in corso...';
  const payload = {
    menu,
    cashier_id: 1,
    print_now: true,
    items: [...cart.values()].map(item => ({product_id: item.product.id, quantity: item.quantity}))
  };
  try {
    const response = await fetch('/api/orders', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(await response.text());
    const result = await response.json();
    cart.clear();
    document.querySelector('#paid-input').value = '';
    renderCart();
    status.textContent = `Ordine #${result.order_number} stampato.`;
  } catch (error) {
    status.textContent = `Errore: ${error.message}`;
  } finally {
    button.disabled = false;
  }
}

document.addEventListener('click', event => {
  const productButton = event.target.closest('[data-product-id]');
  if (productButton) addProduct(Number(productButton.dataset.productId));

  const removeButton = event.target.closest('[data-remove-id]');
  if (removeButton) decrementProduct(Number(removeButton.dataset.removeId));

  const paidButton = event.target.closest('[data-paid]');
  if (paidButton) {
    document.querySelector('#paid-input').value = paidButton.dataset.paid;
    updateChange();
  }
});

document.querySelector('#paid-input').addEventListener('input', updateChange);
document.querySelector('#print-order').addEventListener('click', printOrder);
document.querySelector('#clear-order').addEventListener('click', () => { cart.clear(); renderCart(); });

loadProducts().then(renderCart);
