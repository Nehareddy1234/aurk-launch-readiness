// Resolve independent colour/size controls to the exact existing SKU.
document.querySelectorAll('[data-variant-fields]').forEach(fields => {
  const original = fields.querySelector('[name="variant_id"]');
  const initial = original.selectedOptions[0]?.value ? original.selectedOptions[0] : null;
  const rows = [...original.options].filter(option => option.value);
  const colour = fields.querySelector('[data-colour-select]');
  const size = fields.querySelector('[data-size-select]');
  const form = fields.closest('form');
  function option(text, value) { return new Option(text, value); }
  const colours = new Map(rows.filter(row => !row.disabled).map(row => [row.dataset.colourId, row.dataset.colour]));
  colour.replaceChildren(option('Choose colour', ''));
  colours.forEach((name, id) => colour.add(option(name, id)));
  if (colours.size === 1) colour.value = [...colours.keys()][0];
  function sync() {
    const match = rows.find(row => !row.disabled && row.dataset.colourId === colour.value && row.dataset.sizeId === size.value);
    original.value = match ? match.value : '';
    original.dispatchEvent(new Event('change'));
  }
  function sizes() {
    const previous = size.value;
    size.replaceChildren(option(colour.value ? 'Choose size' : 'Choose colour first', ''));
    const seen = new Set();
    rows.filter(row => row.dataset.colourId === colour.value).forEach(row => {
      if (seen.has(row.dataset.sizeId)) return;
      seen.add(row.dataset.sizeId);
      const entry = option(row.dataset.size + (row.disabled ? ' (Sold out)' : ''), row.dataset.sizeId);
      entry.disabled = row.disabled;
      size.add(entry);
    });
    size.disabled = !colour.value;
    if ([...size.options].some(item => item.value === previous && !item.disabled)) size.value = previous;
    sync();
  }
  colour.required = true;
  size.required = true;
  original.required = false;
  fields.querySelector('[data-combined-label]').hidden = true;
  fields.querySelector('[data-separate-fields]').hidden = false;
  colour.addEventListener('change', sizes);
  size.addEventListener('change', sync);
  form.addEventListener('submit', event => {
    sync();
    if (!original.value) { event.preventDefault(); size.reportValidity(); }
  });
  window.addEventListener('pageshow', sizes);
  if (initial && !initial.disabled) colour.value = initial.dataset.colourId;
  sizes();
  if (initial && !initial.disabled) { size.value = initial.dataset.sizeId; sync(); }
});



document.querySelectorAll('form[data-submit-once]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (event.defaultPrevented) return;
    const button = event.submitter || form.querySelector('button[type="submit"], button:not([type])');
    form.setAttribute('aria-busy', 'true');
    if (button) { button.disabled = true; button.dataset.label = button.textContent; button.textContent = 'Please wait...'; }
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('form[aria-busy]').forEach(form => form.removeAttribute('aria-busy'));
  document.querySelectorAll('button[data-label]').forEach((button) => {
    button.disabled = false; button.textContent = button.dataset.label;
  });
});
document.querySelectorAll('[data-order-status-url]').forEach((panel) => {
  async function refreshStatus() {
    if (document.hidden) { window.setTimeout(refreshStatus, 15000); return; }
    try {
      const response = await fetch(panel.dataset.orderStatusUrl, { headers: { Accept: 'application/json' } });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const data = await response.json();
      panel.querySelector('[data-status-label]').textContent = data.label;
      panel.querySelector('[data-status-message]').textContent = data.message;
      if (['Delivered', 'Cancelled'].includes(data.status)) return;
    } catch (_) { /* The rendered status remains available when offline. */ }
    window.setTimeout(refreshStatus, 15000);
  }
  panel.setAttribute('aria-live', 'polite');
  window.setTimeout(refreshStatus, 15000);
});


document.querySelectorAll('[data-variant-form]').forEach((form) => {
  const select = form.querySelector('[name="variant_id"]');
  const quantity = form.querySelector('[name="quantity"]');
  const price = document.querySelector('[data-variant-price]');
  const stock = form.querySelector('[data-variant-stock]');
  const initialPrice = price.textContent;
  const originalPrice = form.closest('.shopping-product-info').querySelector('[data-original-price]');
  const originalHidden = originalPrice?.hidden;
  form.querySelectorAll('[data-quantity-step]').forEach(button => {
    button.hidden = false;
    button.addEventListener('click', () => {
      const next = (Number(quantity.value) || 1) + Number(button.dataset.quantityStep);
      quantity.value = String(Math.max(1, Math.min(Number(quantity.max) || 99, next)));
      quantity.dispatchEvent(new Event('change'));
    });
  });
  function updateVariant() {
    const option = select.selectedOptions[0];
    if (!option?.value) {
      price.textContent = initialPrice;
      if (originalPrice) originalPrice.hidden = originalHidden;
      stock.textContent = 'Choose an option to see availability.';
      quantity.max = '99';
      return;
    }
    const available = Number(option.dataset.stock);
    if (originalPrice) {
      originalPrice.hidden = !option.dataset.originalPrice;
      if (!originalPrice.hidden) originalPrice.textContent = new Intl.NumberFormat('en-IN', {style:'currency',currency:'INR'}).format(Number(option.dataset.originalPrice));
    }
    price.textContent = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'}).format(Number(option.dataset.price));
    quantity.max = String(available);
    if (Number(quantity.value) > available) quantity.value = String(available);
    stock.textContent = available <= 5 ? `Only ${available} available.` : 'In stock. Ready to order.';
  }
  select.addEventListener('change', updateVariant);
  window.addEventListener('pageshow', updateVariant);
  updateVariant();
});


const menuToggle = document.querySelector('.site-menu-toggle');
const siteHeader = document.querySelector('.site-header');
if (menuToggle && siteHeader) {
  menuToggle.hidden = false;
  siteHeader.dataset.menuOpen = 'false';
  function closeMenu() {
    siteHeader.dataset.menuOpen = 'false';
    menuToggle.setAttribute('aria-expanded', 'false');
  }
  window.matchMedia('(max-width: 1024px)').addEventListener('change', closeMenu);
  document.addEventListener('click', event => {
    if (!siteHeader.contains(event.target)) closeMenu();
  });
  siteHeader.querySelectorAll('nav a').forEach(link => {
    link.addEventListener('click', closeMenu);
  });
  menuToggle.addEventListener('click', () => {
    const open = siteHeader.dataset.menuOpen !== 'true';
    siteHeader.dataset.menuOpen = String(open);
    menuToggle.setAttribute('aria-expanded', String(open));
  });
  siteHeader.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && siteHeader.dataset.menuOpen === 'true') {
      closeMenu(); menuToggle.focus();
    }
  });
}

// Each card owns its selection/quantity state, including repeated home sections.
document.querySelectorAll('[data-quick-add]').forEach(form => {
  const select = form.querySelector('[name="variant_id"]');
  const quantity = form.querySelector('[name="quantity"]');
  const note = form.querySelector('[data-quick-note]');
  function update() {
    const option = select.selectedOptions[0];
    const available = Number(option?.dataset.stock || 99);
    quantity.max = String(available);
    if (Number(quantity.value) > available) quantity.value = String(available);
    note.textContent = option?.value
      ? `${new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'}).format(Number(option.dataset.price))} each` + (available <= 5 ? ` / Only ${available} available` : ' / In stock')
      : 'Choose your size to add it straight to your bag.';
  }
  select.addEventListener('change', update);
  window.addEventListener('pageshow', update);
  update();
});


// Reuse form CSRF tokens; regular form submission also works without JavaScript.
document.querySelectorAll('[data-interest-form]').forEach((form) => {
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    if (button.disabled) return;
    button.disabled = true;
    const message = form.querySelector('[role="status"]');
    message.textContent = 'Registering your interest...';
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), headers: {'Accept': 'application/json'}});
      const result = await response.json();
      if (response.status === 401 && result.login_url) {
        window.location.assign(result.login_url);
        return;
      }
      if (!response.ok || !result.success) throw new Error(result.message || 'Something went wrong. Please try again.');
      document.querySelectorAll('[data-interest-form]').forEach((other) => {
        if (other.action === form.action) {
          other.querySelector('button').disabled = true;
          other.querySelector('button').textContent = other.hasAttribute('data-notify-launch') ? "You're on the list ✓" : 'Interest Registered \u2713';
          other.querySelector('[role="status"]').textContent = result.message;
        }
      });
    } catch (error) {
      button.disabled = false;
      message.textContent = error instanceof SyntaxError ? 'Something went wrong. Please reload and try again.' : error.message;
    }
  });
});

// Scope each photo gallery to its own product, including repeated home cards.
document.querySelectorAll('[data-photo-gallery]').forEach(gallery => {
  const photo = gallery.querySelector('.shopping-image-link img, .home-product-image img, .product-card-image img');
  const options = [...gallery.querySelectorAll('[data-photo-source]')];
  if (!photo || options.length < 2) return;
  let index = Math.max(0, options.findIndex(button => button.getAttribute('aria-pressed') === 'true'));
  const count = gallery.querySelector('[data-photo-count]');
  const surface = photo.closest('a');
  const track = document.createElement('span');
  track.className = 'product-photo-track';
  options.forEach(option => {
    const image = document.createElement('img');
    image.src = option.dataset.photoSource;
    image.alt = option.dataset.photoAlt;
    image.draggable = false;
    image.loading = 'lazy';
    track.append(image);
  });
  photo.replaceWith(track);
  surface.classList.add('product-photo-slider');
  surface.setAttribute('aria-label', 'Drag or swipe to change product photo. Click to open photo.');
  let gesture = null;
  let blockClickUntil = 0;
  let hoverRestoreIndex = null;
  if (gallery.classList.contains('home-product-card')) {
    surface.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'mouse' || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
      hoverRestoreIndex = index;
      show(index + 1);
    });
    surface.addEventListener('pointerleave', () => {
      if (hoverRestoreIndex === null) return;
      show(hoverRestoreIndex);
      hoverRestoreIndex = null;
    });
  }
  surface.addEventListener('dragstart', event => event.preventDefault());
  surface.addEventListener('pointerdown', event => {
    if (event.pointerType === 'touch') return;
    if (!event.isPrimary || event.button !== 0) return;
    hoverRestoreIndex = null;
    gesture = {id: event.pointerId, x: event.clientX, y: event.clientY, dx: 0, dragging: false};
  });
  surface.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') return;
    if (!gesture || event.pointerId !== gesture.id) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    if (!gesture.dragging && Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 10) { gesture = null; return; }
    if (!gesture.dragging && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy)) {
      gesture.dragging = true;
      if (!gesture.touch) surface.setPointerCapture(event.pointerId);
      surface.classList.add('is-dragging');
    }
    if (!gesture.dragging) return;
    if (event.cancelable) event.preventDefault();
    gesture.dx = dx;
    track.style.transform = 'translateX(calc(' + (-index * 100) + '% + ' + dx + 'px))';
  });
  function finish(event, cancelled = false) {
    if (!gesture || event.pointerId !== gesture.id) return;
    const previous = gesture;
    gesture = null;
    surface.classList.remove('is-dragging');
    if (!previous.touch && surface.hasPointerCapture(event.pointerId)) surface.releasePointerCapture(event.pointerId);
    if (previous.dragging) {
      blockClickUntil = Date.now() + 400;
      const threshold = Math.min(80, surface.clientWidth * .18);
      show(!cancelled && Math.abs(previous.dx) >= threshold ? index + (previous.dx < 0 ? 1 : -1) : index);
    }
  }
  surface.addEventListener('pointerup', event => { if (!gesture?.touch) finish(event); });
  surface.addEventListener('pointercancel', event => { if (!gesture?.touch) finish(event, true); });
  surface.addEventListener('lostpointercapture', event => { if (!gesture?.touch) finish(event, true); });
  surface.addEventListener('touchstart', event => {
    if (event.touches.length !== 1) { if (gesture?.touch) finish({pointerId: gesture.id}, true); return; }
    const touch = event.touches[0];
    gesture = {id: touch.identifier, x: touch.clientX, y: touch.clientY, dx: 0, dragging: false, touch: true};
  }, {passive: true});
  surface.addEventListener('touchmove', event => {
    if (!gesture?.touch) return;
    const touch = [...event.touches].find(item => item.identifier === gesture.id);
    if (!touch) return;
    const dx = touch.clientX - gesture.x;
    const dy = touch.clientY - gesture.y;
    if (!gesture.dragging && Math.abs(dy) > Math.abs(dx) && Math.abs(dy) > 10) { gesture = null; return; }
    if (!gesture.dragging && Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy)) {
      gesture.dragging = true;
      surface.classList.add('is-dragging');
    }
    if (!gesture.dragging) return;
    if (event.cancelable) event.preventDefault();
    gesture.dx = dx;
    track.style.transform = 'translateX(calc(' + (-index * 100) + '% + ' + dx + 'px))';
  }, {passive: false});
  surface.addEventListener('touchend', event => {
    if (!gesture?.touch) return;
    if ([...event.changedTouches].some(touch => touch.identifier === gesture.id)) finish({pointerId: gesture.id});
  });
  surface.addEventListener('touchcancel', () => { if (gesture?.touch) finish({pointerId: gesture.id}, true); });
  surface.addEventListener('click', event => {
    if (Date.now() < blockClickUntil) { event.preventDefault(); event.stopPropagation(); }
  }, true);

  function show(next) {
    index = (next + options.length) % options.length;
    track.style.transform = 'translateX(' + (-index * 100) + '%)';
    const full = gallery.querySelector('.shopping-image-link');
    if (full) full.href = options[index].dataset.photoSource;
    options.forEach((button, position) => button.setAttribute('aria-pressed', String(position === index)));
    count.textContent = 'Photo ' + (index + 1) + ' of ' + options.length;
  }
  options.forEach((button, position) => button.addEventListener('click', () => {
    hoverRestoreIndex = null;
    show(position);
  }));
  const previousButton = gallery.querySelector('[data-photo-prev]');
  const nextButton = gallery.querySelector('[data-photo-next]');
  if (previousButton && nextButton) {
    previousButton.hidden = nextButton.hidden = false;
    previousButton.addEventListener('click', () => show(index - 1));
    nextButton.addEventListener('click', () => show(index + 1));
  }

  gallery.querySelector('[data-photo-controls]').addEventListener('keydown', event => {
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault();
      show(index + (event.key === 'ArrowLeft' ? -1 : 1));
      options[index].focus();
    }
  });
  show(index);
  if (gallery.classList.contains('shopping-gallery')) {
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    window.setInterval(() => {
      if (document.hidden || motion.matches || gesture || gallery.matches(':hover') || gallery.contains(document.activeElement)) return;
      show(index + 1);
    }, 5000);
  }
});
