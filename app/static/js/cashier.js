const cashierRoot = document.querySelector('.cashier');
const menu = cashierRoot.dataset.menu;
const cashierId = Number(cashierRoot.dataset.cashierId || 1);
const cart = new Map();
let products = [];
let visibleCategoryNames = new Set();
const displayOptions = { name: true, icon: true, price: true };

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
  visibleCategoryNames = new Set(getCategories().map(category => category.name));
  renderCategoryFilters();
  syncCategoryFilterButtons();
  syncDisplayOptionButtons();
  renderProducts();
}

function normalizeSearch(value) {
  return String(value || '').trim().toLowerCase();
}

function getCategories() {
  const byName = new Map();
  for (const product of products) {
    const name = product.category_name || 'Senza categoria';
    if (!byName.has(name)) {
      byName.set(name, {
        name,
        sortOrder: numericSortValue(product.category_sort_order),
        count: 0
      });
    }
    byName.get(name).count += 1;
  }
  return [...byName.values()].sort((a, b) => a.sortOrder - b.sortOrder || a.name.localeCompare(b.name, 'it'));
}

function productMatchesSearch(product, query) {
  if (!query) return true;
  return [
    product.name,
    product.name_short,
    product.slug,
    product.acronym,
    product.category_name
  ].some(value => normalizeSearch(value).includes(query));
}

function getFilteredProducts() {
  const query = normalizeSearch(document.querySelector('#product-search')?.value);
  return products.filter(product => {
    const categoryName = product.category_name || 'Senza categoria';
    return visibleCategoryNames.has(categoryName) && productMatchesSearch(product, query);
  });
}

function renderCategoryFilters() {
  const target = document.querySelector('#category-filters');
  if (!target) return;
  target.innerHTML = getCategories().map(category => `
    <button type="button" class="category-filter active" data-category-name="${escapeHtml(category.name)}" aria-pressed="true">
      ${escapeHtml(category.name)} <span>${category.count}</span>
    </button>
  `).join('');
}

function syncCategoryFilterButtons() {
  document.querySelectorAll('.category-filter[data-category-name]').forEach(button => {
    const isActive = visibleCategoryNames.has(button.dataset.categoryName);
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-pressed', String(isActive));
  });
  syncCategoryToggleAllButton();
}

function syncCategoryToggleAllButton() {
  const button = document.querySelector('#toggle-all-categories');
  if (!button) return;
  const categories = getCategories();
  const allSelected = categories.length > 0 && categories.every(category => visibleCategoryNames.has(category.name));
  button.textContent = allSelected ? 'Deseleziona tutto' : 'Seleziona tutto';
  button.setAttribute('aria-pressed', String(allSelected));
}

function syncDisplayOptionButtons() {
  document.querySelectorAll('[data-display-option]').forEach(button => {
    const option = button.dataset.displayOption;
    button.classList.toggle('active', Boolean(displayOptions[option]));
    button.setAttribute('aria-pressed', String(Boolean(displayOptions[option])));
  });
  syncDisplayToggleAllButton();
}

function syncDisplayToggleAllButton() {
  const button = document.querySelector('#toggle-all-display-options');
  if (!button) return;
  const allSelected = Object.values(displayOptions).every(Boolean);
  button.textContent = allSelected ? 'Deseleziona tutto' : 'Seleziona tutto';
  button.setAttribute('aria-pressed', String(allSelected));
}

function updateDisplayClasses() {
  cashierRoot.classList.toggle('hide-product-names', !displayOptions.name);
  cashierRoot.classList.toggle('hide-product-icons', !displayOptions.icon);
  cashierRoot.classList.toggle('hide-product-prices', !displayOptions.price);
  syncDisplayOptionButtons();
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function getCartQuantity(productId) {
  return cart.get(productId)?.quantity || 0;
}

function productButtonQuantityBadge(quantity) {
  if (quantity <= 0) return '';
  return `<span class="cart-quantity-badge" aria-label="Quantità nel carrello: ${quantity}">${quantity}</span>`;
}

function updateProductButtonsFromCart() {
  document.querySelectorAll('.product-button[data-product-id]').forEach(button => {
    const productId = Number(button.dataset.productId);
    const quantity = getCartQuantity(productId);
    button.classList.toggle('in-cart', quantity > 0);
    button.dataset.cartQuantity = String(quantity);

    const currentBadge = button.querySelector('.cart-quantity-badge');
    if (quantity > 0) {
      if (currentBadge) {
        currentBadge.textContent = String(quantity);
        currentBadge.setAttribute('aria-label', `Quantità nel carrello: ${quantity}`);
      } else {
        button.insertAdjacentHTML('beforeend', productButtonQuantityBadge(quantity));
      }
    } else if (currentBadge) {
      currentBadge.remove();
    }
  });
}

function renderProducts() {
  const grid = document.querySelector('#product-grid');
  const emptyMessage = document.querySelector('#empty-products-message');
  const filteredProducts = getFilteredProducts();
  grid.innerHTML = filteredProducts.map(product => {
    const displayName = product.name_short || product.name;
    const imagePath = product.image_path || `/static/img/products/${product.slug}.png`;
    const fallback = escapeHtml(product.acronym || displayName.slice(0, 2).toUpperCase());
    const quantity = getCartQuantity(product.id);
    const inCartClass = quantity > 0 ? ' in-cart' : '';
    return `
      <button class="product-button${inCartClass}" data-product-id="${product.id}" data-category-name="${escapeHtml(product.category_name || '')}" data-cart-quantity="${quantity}">
        <span class="product-image-wrap">
          <img class="product-image" src="${escapeHtml(imagePath)}" alt="" loading="lazy" onerror="this.remove(); this.parentElement.textContent='${fallback}';">
        </span>
        <strong class="name">${escapeHtml(displayName)}</strong>
        <span class="price">${money(product.price_cents)}</span>
        ${productButtonQuantityBadge(quantity)}
      </button>
    `;
  }).join('');
  if (emptyMessage) emptyMessage.hidden = filteredProducts.length > 0;
  updateDisplayClasses();
}

function addProduct(productId) {
  const product = products.find(item => item.id === productId);
  if (!product) return;
  const current = cart.get(productId) ?? { product, quantity: 0 };
  current.quantity += 1;
  cart.set(productId, current);
  renderCart(productId);
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

function renderCart(highlightProductId = null) {
  const lines = document.querySelector('#cart-lines');
  lines.innerHTML = getCartItemsInMenuOrder().map(item => {
    const displayName = item.product.name_short || item.product.name;
    const escapedName = escapeHtml(displayName);
    const highlightClass = item.product.id === highlightProductId ? ' cart-line-highlight' : '';
    return `
      <div class="cart-line${highlightClass}" data-cart-line-product-id="${item.product.id}">
        <div class="cart-product">
          <strong>${escapedName}</strong>
          <span>${money(item.product.price_cents)}</span>
        </div>
        <div class="quantity-controls" aria-label="Quantità ${escapedName}">
          <button type="button" data-decrement-id="${item.product.id}" aria-label="Diminuisci ${escapedName}">−</button>
          <span class="quantity">${item.quantity}</span>
          <button type="button" data-increment-id="${item.product.id}" aria-label="Aumenta ${escapedName}">+</button>
          <button type="button" data-delete-id="${item.product.id}" aria-label="Rimuovi ${escapedName}">×</button>
        </div>
        <strong class="line-total">${money(item.product.price_cents * item.quantity)}</strong>
      </div>
    `;
  }).join('') || '<p>Nessun prodotto selezionato.</p>';

  const total = getTotalCents();
  document.querySelector('#cart-total').textContent = money(total);
  document.querySelector('#quick-paid').innerHTML = quickPaidValues(total).map(v => `<button data-paid="${v}">€ ${v}</button>`).join('');
  updateChange();
  updateProductButtonsFromCart();
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


function toggleCashierPanel(toggleButton, panel) {
  if (!toggleButton || !panel) return;
  const isOpen = !panel.hidden;
  panel.hidden = isOpen;
  toggleButton.classList.toggle('active', !isOpen);
  toggleButton.setAttribute('aria-expanded', String(!isOpen));
}

function handleCashierToolbarToggle(event) {
  const toolsToggle = event.target.closest('#cashier-tools-toggle');
  if (toolsToggle) {
    toggleCashierPanel(toolsToggle, document.querySelector('#cashier-tools-panel'));
    return true;
  }

  return false;
}

document.addEventListener('click', event => {
  if (handleCashierToolbarToggle(event)) return;

  const categoryToggleAllButton = event.target.closest('#toggle-all-categories');
  if (categoryToggleAllButton) {
    const categories = getCategories();
    const allSelected = categories.length > 0 && categories.every(category => visibleCategoryNames.has(category.name));
    visibleCategoryNames = allSelected ? new Set() : new Set(categories.map(category => category.name));
    syncCategoryFilterButtons();
    renderProducts();
    return;
  }

  const categoryButton = event.target.closest('[data-category-name].category-filter');
  if (categoryButton) {
    const categoryName = categoryButton.dataset.categoryName;
    if (visibleCategoryNames.has(categoryName)) {
      visibleCategoryNames.delete(categoryName);
    } else {
      visibleCategoryNames.add(categoryName);
    }
    syncCategoryFilterButtons();
    renderProducts();
    return;
  }

  const displayToggleAllButton = event.target.closest('#toggle-all-display-options');
  if (displayToggleAllButton) {
    const allSelected = Object.values(displayOptions).every(Boolean);
    Object.keys(displayOptions).forEach(option => {
      displayOptions[option] = !allSelected;
    });
    updateDisplayClasses();
    return;
  }

  const displayButton = event.target.closest('[data-display-option]');
  if (displayButton) {
    const option = displayButton.dataset.displayOption;
    displayOptions[option] = !displayOptions[option];
    updateDisplayClasses();
    return;
  }

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

function setupCashierFrontendControls() {
  const searchInput = document.querySelector('#product-search');
  if (searchInput) searchInput.addEventListener('input', renderProducts);
}

document.querySelector('#paid-input').addEventListener('input', updateChange);
document.querySelector('#print-order').addEventListener('click', printOrder);
document.querySelector('#clear-order').addEventListener('click', () => { cart.clear(); renderCart(); });
setupCashierFrontendControls();

loadProducts().then(renderCart);
