const kitchenRoot = document.querySelector('.kitchen-screen');
const screenSlug = kitchenRoot.dataset.screenSlug;
let previousTotals = new Map();
let hasPreviousTotals = false;

function productLabel(product) {
  return product.name_short || product.name;
}

function isProductEnabled(product) {
  return product && product.enabled !== false && product.enabled !== 0 && product.enabled !== '0';
}

function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function renderDelta(delta, enabled = true) {
  if (!enabled) return '<span class="delta delta-disabled">OFF</span>';
  if (!hasPreviousTotals || delta === 0) return '<span class="delta delta-zero">—</span>';
  const sign = delta > 0 ? '+' : '';
  return `<span class="delta ${delta > 0 ? 'delta-up' : 'delta-down'}">${sign}${delta}</span>`;
}

function mergeKitchenProducts(totalsData, adminScreens, adminProducts) {
  const screen = adminScreens.find(item => item.slug === screenSlug);
  if (!screen) return totalsData.products;

  const productsById = new Map(adminProducts.map(product => [Number(product.id), product]));
  const totalsById = new Map(totalsData.products.map(product => [Number(product.id), product]));

  return screen.product_ids.map(productId => {
    const id = Number(productId);
    const product = productsById.get(id) || totalsById.get(id);
    if (!product) return null;

    const totalProduct = totalsById.get(id);
    return {
      ...product,
      image_path: product.image_path || product.resolved_image_path || `/static/img/products/${product.slug}.png`,
      quantity_total: totalProduct ? totalProduct.quantity_total : 0,
    };
  }).filter(Boolean);
}


function stockStatusLabel(status) {
  if (status === 'insufficient') return 'INSUFFICIENTE';
  if (status === 'low') return 'IN ESAURIMENTO';
  if (status === 'untracked') return 'Non monitorato';
  return 'OK';
}

function renderStockItems(items = []) {
  const target = document.querySelector('#kitchen-stock-grid');
  if (!target) return;
  const trackedItems = items.filter(item => item.tracked);
  target.innerHTML = trackedItems.map(item => `
    <article class="stock-card stock-card-${escapeHtml(item.status)}">
      <strong>${escapeHtml(item.name)}</strong>
      <div class="stock-values" aria-label="Riepilogo stock ${escapeHtml(item.name)}">
        <span><small>Totali</small><b>${escapeHtml(item.initial_quantity_display)}</b></span>
        <span><small>Consumati</small><b>${escapeHtml(item.consumed_display)}</b></span>
        <span><small>Rimasti</small><b>${escapeHtml(item.remaining_display)}</b></span>
      </div>
      <span class="stock-unit">${escapeHtml(item.unit_name)}</span>
      <em>${stockStatusLabel(item.status)}</em>
    </article>
  `).join('') || '<p>Nessuno stock monitorato per oggi.</p>';
}

function renderProducts(products) {
  const grid = document.querySelector('#kitchen-grid');
  grid.innerHTML = products.map(product => {
    const enabled = isProductEnabled(product);
    const quantity = enabled ? Number(product.quantity_total || 0) : 0;
    const previousQuantity = previousTotals.get(product.id) ?? quantity;
    const delta = quantity - previousQuantity;
    const label = productLabel(product);
    const fallback = escapeHtml(product.acronym || label.slice(0, 2).toUpperCase());
    const imagePath = product.image_path || product.resolved_image_path || `/static/img/products/${product.slug}.png`;
    const disabledClass = enabled ? '' : ' kitchen-card-disabled';
    return `
      <article class="kitchen-card${disabledClass}" data-product-id="${product.id}" aria-disabled="${String(!enabled)}">
        <span class="kitchen-image-wrap">
          <img class="kitchen-image" src="${escapeHtml(imagePath)}" alt="" loading="lazy" onerror="this.remove(); this.parentElement.textContent='${fallback}';">
        </span>
        <div class="kitchen-info">
          <strong>${escapeHtml(label)}</strong>
          <span>${escapeHtml(product.name)}</span>
          ${enabled ? '' : '<em>Terminato</em>'}
        </div>
        <div class="kitchen-quantity">
          <span class="quantity">${quantity}</span>
          ${renderDelta(delta, enabled)}
        </div>
      </article>
    `;
  }).join('') || '<p>Nessun prodotto associato a questa schermata.</p>';
}

async function loadData() {
  const status = document.querySelector('#kitchen-status');
  try {
    const [totalsResponse, adminScreensResponse, adminProductsResponse] = await Promise.all([
      fetch(`/api/kitchen-screens/${encodeURIComponent(screenSlug)}/totals`),
      fetch('/api/kitchen-screens/admin'),
      fetch('/api/products/admin'),
    ]);
    if (!totalsResponse.ok) throw new Error(await totalsResponse.text());
    const totalsData = await totalsResponse.json();
    let products = totalsData.products;

    if (adminScreensResponse.ok && adminProductsResponse.ok) {
      const [adminScreens, adminProducts] = await Promise.all([
        adminScreensResponse.json(),
        adminProductsResponse.json(),
      ]);
      products = mergeKitchenProducts(totalsData, adminScreens, adminProducts);
    }

    renderProducts(products);
    renderStockItems(totalsData.stock_items || []);
    document.querySelector('#kitchen-total').textContent = products
      .filter(isProductEnabled)
      .reduce((sum, product) => sum + Number(product.quantity_total || 0), 0);
    previousTotals = new Map(products.map(product => [product.id, isProductEnabled(product) ? Number(product.quantity_total || 0) : 0]));
    hasPreviousTotals = true;
    status.textContent = `Aggiornato: ${new Date().toLocaleTimeString('it-IT')}`;
  } catch (error) {
    status.textContent = `Errore aggiornamento: ${error.message}`;
  }
}

loadData();
setInterval(loadData, 3000);
