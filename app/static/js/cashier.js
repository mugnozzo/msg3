const cashierRoot = document.querySelector('.cashier');
const menu = cashierRoot.dataset.menu;
const cashierId = Number(cashierRoot.dataset.cashierId || 1);
const cart = new Map();
let products = [];

const money = cents => `€ ${(cents / 100).toFixed(2).replace('.', ',')}`;

const numericSortValue = value => {
  const number = Number(value);
  return Number.isFinite(number) ? number : Number.MAX_SAFE_INTEGER;
};

function compareProductsByMenuOrder(a, b) {
  return numericSortValue(a.category_sort_order) - numericSortValue(b.category_sort_order)
    || numericSortValue(a.menu_sort_order) - numericSortValue(b.menu_sort_order)
    || numericSortValue(a.product_sort_order) - numericSortValue(b.product_sort_order)
    || String(a.name_short || a.name).localeCompare(String(b.name_short || b.name), 'it')
    || numericSortValue(a.id) - numericSortValue(b.id);
}

async function loadProducts() {
  const response = await fetch(`/api/products?menu=${encodeURIComponent(menu)}`);
  products = await response.json();
  renderProducts();
}

function renderProducts() {
  const grid = document.querySelector('#product-grid');
  grid.innerHTML = products.map(product => {
    const displayName = product.name_short || product.name;
    const imagePath = product.image_path || `/static/img/products/${product.slug}.png`;
    const fallback = product.acronym || displayName.slice(0, 2).toUpperCase();
    return `
      <button class="product-button" data-product-id="${product.id}">
        <span class="product-image-wrap">
          <img class="product-image" src="${imagePath}" alt="" loading="lazy" onerror="this.remove(); this.parentElement.textContent='${fallback}';">
        </span>
        <strong class="name">${displayName}</strong>
        <span class="price">${money(product.price_cents)}</span>
      </button>
    `;
  }).join('');
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

function removeProduct(productId) {
  cart.delete(productId);
  renderCart();
}

function getCartItemsInMenuOrder() {
  return [...cart.values()].sort((a, b) => compareProductsByMenuOrder(a.product, b.product));
}

function getTotalCents() {
  return getCartItemsInMenuOrder().reduce((sum, item) => sum + item.product.price_cents * item.quantity, 0);
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
  lines.innerHTML = getCartItemsInMenuOrder().map(item => `
    <div class="cart-line">
      <div class="cart-product">
        <strong>${item.product.name_short || item.product.name}</strong>
        <span>${money(item.product.price_cents)} cad.</span>
      </div>
      <div class="quantity-controls" aria-label="Quantità ${item.product.name_short || item.product.name}">
        <button type="button" data-decrement-id="${item.product.id}" aria-label="Diminuisci ${item.product.name_short || item.product.name}">−</button>
        <span class="quantity">${item.quantity}</span>
        <button type="button" data-increment-id="${item.product.id}" aria-label="Aumenta ${item.product.name_short || item.product.name}">+</button>
        <button type="button" data-delete-id="${item.product.id}" aria-label="Rimuovi ${item.product.name_short || item.product.name}">×</button>
      </div>
      <strong class="line-total">${money(item.product.price_cents * item.quantity)}</strong>
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
    cashier_id: cashierId,
    print_now: true,
    items: getCartItemsInMenuOrder().map(item => ({product_id: item.product.id, quantity: item.quantity}))
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

  const decrementButton = event.target.closest('[data-decrement-id]');
  if (decrementButton) decrementProduct(Number(decrementButton.dataset.decrementId));

  const incrementButton = event.target.closest('[data-increment-id]');
  if (incrementButton) addProduct(Number(incrementButton.dataset.incrementId));

  const deleteButton = event.target.closest('[data-delete-id]');
  if (deleteButton) removeProduct(Number(deleteButton.dataset.deleteId));

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
