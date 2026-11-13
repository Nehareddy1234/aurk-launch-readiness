/* Keep navigation available on touch screens and while shopping. */
(() => {
  const header = document.getElementById('aurk-header');
  if (!header) return;
  let scheduled = false;
  function update() {
    header.dataset.scrolled = String(window.scrollY > (document.body.classList.contains('home-page') ? 0 : 24));
    scheduled = false;
  }
  window.addEventListener('scroll', () => {
    if (!scheduled) { scheduled = true; requestAnimationFrame(update); }
  }, {passive: true});
  update();
})();
