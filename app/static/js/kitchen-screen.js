const kitchenRoot = document.querySelector('.kitchen-screen');
const screenSlug = kitchenRoot.dataset.screenSlug;
let previousTotals = new Map();
let hasPreviousTotals = false;

function productLabel(product) {
  return product.name_short || product.name;
}

function renderDelta(delta) {
  if (!hasPreviousTotals || delta === 0) return '<span class="delta delta-zero">—</span>';
  const sign = delta > 0 ? '+' : '';
  return `<span class="delta ${delta > 0 ? 'delta-up' : 'delta-down'}">${sign}${delta}</span>`;
}

function renderProducts(products) {
  const grid = document.querySelector('#kitchen-grid');
  grid.innerHTML = products.map(product => {
    const quantity = Number(product.quantity_total || 0);
    const previousQuantity = previousTotals.get(product.id) ?? quantity;
    const delta = quantity - previousQuantity;
    const label = productLabel(product);
    const fallback = product.acronym || label.slice(0, 2).toUpperCase();
    return `
      <article class="kitchen-card" data-product-id="${product.id}">
        <span class="kitchen-image-wrap">
          <img class="kitchen-image" src="${product.image_path}" alt="" loading="lazy" onerror="this.remove(); this.parentElement.textContent='${fallback}';">
        </span>
        <div class="kitchen-info">
          <strong>${label}</strong>
          <span>${product.name}</span>
        </div>
        <div class="kitchen-quantity">
          <span class="quantity">${quantity}</span>
          ${renderDelta(delta)}
        </div>
      </article>
    `;
  }).join('') || '<p>Nessun prodotto associato a questa schermata.</p>';
}

async function loadData() {
  const status = document.querySelector('#kitchen-status');
  try {
    const response = await fetch(`/api/kitchen-screens/${encodeURIComponent(screenSlug)}/totals`);
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    renderProducts(data.products);
    document.querySelector('#kitchen-total').textContent = data.total_items;
    previousTotals = new Map(data.products.map(product => [product.id, Number(product.quantity_total || 0)]));
    hasPreviousTotals = true;
    status.textContent = `Aggiornato: ${new Date().toLocaleTimeString('it-IT')}`;
  } catch (error) {
    status.textContent = `Errore aggiornamento: ${error.message}`;
  }
}

loadData();
setInterval(loadData, 3000);
