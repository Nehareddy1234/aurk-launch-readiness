/* Progressive enhancement: content remains visible if animation is unavailable. */
(() => {
  if (!document.body.classList.contains('storefront-theme')) return;
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const campaign = document.querySelector('[data-campaign-src]');
  if (campaign) {
    const updateCampaign = () => {
      if (preference.matches) {
        campaign.pause();
        campaign.hidden = true;
        campaign.removeAttribute('src');
        campaign.load();
        return;
      }
      campaign.src = campaign.dataset.campaignSrc;
      campaign.play().catch(() => {});
    };
    campaign.addEventListener('playing', () => {
      campaign.hidden = preference.matches;
    });
    preference.addEventListener('change', updateCampaign);
    updateCampaign();
  }
  if (preference.matches || !('IntersectionObserver' in window) || !Element.prototype.animate) return;
  const animations = new Set();
  const menu = document.querySelector('.site-menu-toggle');
  if (menu) menu.addEventListener('click', () => {
    if (preference.matches || menu.getAttribute('aria-expanded') !== 'true') return;
    const navigation = document.getElementById('store-navigation');
    if (!navigation) return;
    const animation = navigation.animate([{opacity:0, transform:'translateY(-6px)'}, {opacity:1, transform:'translateY(0)'}], {duration:220, easing:'ease-out'});
    animations.add(animation);
    animation.onfinish = () => animations.delete(animation);
  });
  const targets = document.querySelectorAll('.storefront-hero-copy, .storefront-hero-feature, .storefront-section-heading, .home-collections > a, .home-product-card, .home-cod-story, .home-cod-story li, .shop-header, .product-card, .commerce-heading, .storefront-benefits, .category-filter, .shop-toolbar');
  const observer = new IntersectionObserver((entries) => {
    let revealIndex = 0;
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      if (preference.matches) return;
      // Only count entering elements, so offscreen entries do not alter the stagger.
      const delay = Math.min(revealIndex++, 3) * 45;
      const animation = entry.target.animate([
        {opacity:0, transform:'translateY(16px)'},
        {opacity:1, transform:'translateY(0)'}
      ], {duration:500, delay, easing:'cubic-bezier(.16,1,.3,1)', fill:'backwards'});
      animations.add(animation);
      animation.onfinish = () => animations.delete(animation);
    });
  }, {threshold:0.06});
  targets.forEach((element) => observer.observe(element));
  preference.addEventListener('change', (event) => {
    if (event.matches) { observer.disconnect(); animations.forEach(animation => animation.cancel()); animations.clear(); }
  });
})();
