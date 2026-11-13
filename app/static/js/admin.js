"use strict";
const menu = document.querySelector(".admin-menu-toggle");
if (menu) {
  menu.hidden = false;
  document.body.classList.add("admin-nav-ready");
  menu.addEventListener("click", () => {
    const open = document.body.classList.toggle("admin-menu-open");
    menu.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && document.body.classList.contains("admin-menu-open")) {
      document.body.classList.remove("admin-menu-open");
      menu.setAttribute("aria-expanded", "false");
      menu.focus();
    }
  });
}
// Native form submissions retain browser network error/retry behavior. No optimistic mutations.
document.querySelectorAll('form[method="post"]').forEach(form => {
  form.addEventListener("submit", event => {
    if (event.defaultPrevented) return;
    // Defer disabling until the clicked button's name/value has been serialized.
    window.setTimeout(() => {
      form.setAttribute("aria-busy", "true");
      form.querySelectorAll('button[type="submit"],button:not([type])').forEach(button => {
        button.dataset.originalText = button.textContent;
        button.disabled = true;
        button.textContent = "Saving...";
      });
    }, 0);
  });
});
window.addEventListener("pageshow", () => {
  document.querySelectorAll("form[aria-busy]").forEach(form => form.removeAttribute("aria-busy"));
  document.querySelectorAll("button[data-original-text]").forEach(button => {
    button.disabled = false;
    button.textContent = button.dataset.originalText;
    delete button.dataset.originalText;
  });
});

// Keep files across repeated picker selections and allow removal before saving.
document.querySelectorAll('[data-image-upload]').forEach(input => {
  if (typeof DataTransfer === 'undefined') return;
  let files = [];
  let urls = [];
  const list = input.closest('form').querySelector('[data-upload-list]');
  function render() {
    urls.forEach(url => URL.revokeObjectURL(url));
    urls = [];
    const transfer = new DataTransfer();
    files.forEach(file => transfer.items.add(file));
    input.files = transfer.files;
    const tooMany = files.length + Number(input.dataset.existingCount) > 10;
    const tooLarge = files.reduce((sum, file) => sum + file.size, 0) > 100 * 1024 * 1024;
    const invalidSize = files.some(file => file.size > ((file.type === 'video/mp4' || /\.mp4$/i.test(file.name)) ? 25 : 8) * 1024 * 1024);
    input.setCustomValidity(invalidSize ? 'Photos must be 8 MB or smaller; videos must be 25 MB or smaller.' : tooMany ? 'A product can have at most 10 photos or videos. Remove some files.' : tooLarge ? 'Keep the total upload under 100 MB.' : '');
    list.replaceChildren();
    files.forEach((file, index) => {
      const item = document.createElement('div');
      item.className = 'upload-photo';
      const image = document.createElement(file.type === 'video/mp4' || /\.mp4$/i.test(file.name) ? 'video' : 'img');
      if (image.tagName === 'VIDEO') { image.controls = true; image.preload = 'metadata'; }
      const url = URL.createObjectURL(file);
      urls.push(url);
      image.src = url;
      image.alt = file.name;
      const label = document.createElement('span');
      label.textContent = file.name;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', 'Remove ' + file.name);
      remove.addEventListener('click', () => { files.splice(index, 1); render(); });
      item.append(image, label, remove);
      list.append(item);
    });
  }
  input.addEventListener('change', () => {
    [...input.files].forEach(file => {
      if (!files.some(existing => existing.name === file.name && existing.size === file.size && existing.lastModified === file.lastModified)) files.push(file);
    });
    render();
  });
});
document.querySelectorAll('[data-product-pricing]').forEach(fields => {
  const base = fields.querySelector('[name="base_price"]');
  const discount = fields.querySelector('[name="discount_percent"]');
  const preview = fields.querySelector('[data-price-preview]');
  const status = fields.closest('form').querySelector('[name="product_status"]');
  const hide = fields.querySelector('[name="hide_price"]');
  function update() {
    const comingSoon = status?.value === 'coming_soon';
    const option = fields.querySelector('[data-coming-soon-price-option]');
    if (option) option.hidden = !comingSoon;
    if (hide) hide.disabled = !comingSoon;
    base.required = !(comingSoon && hide?.checked);
    if (comingSoon && hide?.checked) {
      preview.textContent = 'Price is hidden from customers. You can leave it empty.';
      return;
    }
    if (!base.value || !base.validity.valid || !discount.validity.valid) {
      preview.textContent = 'Enter a total price and an optional discount from 0 to 100%.';
      return;
    }
    const amount = Number(base.value) * (1 - Number(discount.value || 0) / 100);
    preview.textContent = 'Selling price: ' + new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'}).format(amount);
  }
  status?.addEventListener('change', update);
  hide?.addEventListener('change', update);
  base.addEventListener('input', update);
  discount.addEventListener('input', update);
  update();
});
