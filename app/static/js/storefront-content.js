// Give every decorative cover video a pause control and respect reduced motion.
document.querySelectorAll('[data-cover-playlist]').forEach(track => {
  const videos = [...track.querySelectorAll('video')];
  const toggle = track.closest('section')?.querySelector('[data-cover-toggle]');
  if (!toggle) return;
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let paused = motion.matches;
  function update() {
    track.dataset.paused = String(paused);
    toggle.hidden = false;
    toggle.setAttribute('aria-pressed', String(paused));
    toggle.textContent = paused ? 'Play background video' : 'Pause background video';
    videos.forEach((video, index) => {
      if (paused || index !== Number(track.dataset.activeVideo || 0)) video.pause();
      else video.play().catch(() => {});
    });
  }
  videos.forEach(video => video.addEventListener('play', () => {
    if (paused) video.pause();
  }));
  toggle.addEventListener('click', () => { paused = !paused; update(); });
  motion.addEventListener('change', () => { paused = motion.matches; update(); });
  update();
});

document.querySelectorAll('[data-cover-playlist]').forEach((track) => {
  const videos = [...track.querySelectorAll('video')];
  if (videos.length < 2) return;
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let active = 0;
  track.dataset.activeVideo = '0';
  videos.forEach((video, index) => {
    video.loop = false;
    video.inert = index !== 0;
    video.addEventListener('ended', () => {
      if (index !== active) return;
      video.pause();
      video.currentTime = 0;
      video.inert = true;
      active = (active + 1) % videos.length;
      const next = videos[active];
      next.inert = false;
      next.currentTime = 0;
      track.style.transform = `translateX(-${active * 100}%)`;
      track.dataset.activeVideo = String(active);
      if (!motion.matches && track.dataset.paused !== 'true') next.play().catch(() => {
        next.controls = true;
        next.removeAttribute('aria-hidden');
        next.setAttribute('aria-label', 'Store cover video');
      });
    });
  });
});

document.querySelectorAll('[data-banner-carousel]').forEach((carousel) => {
  const viewport = carousel.querySelector('.banner-viewport');
  const slides = [...carousel.querySelectorAll('.banner-slide')];
  if (slides.length < 2) return;
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let index = 0;
  let timer;
  let scrollTimer;
  let hovered = false;
  let touching = false;
  function schedule() {
    clearTimeout(timer);
    if (!hovered && !touching && !document.hidden && !motion.matches && !carousel.contains(document.activeElement)) {
      timer = setTimeout(() => {
        if (!hovered && !touching && !document.hidden && !motion.matches && !carousel.contains(document.activeElement)) show(index + 1);
        else schedule();
      }, 5000);
    }
  }
  function update() {
    carousel.dataset.activeBanner = String(index);
    slides.forEach((slide, n) => { slide.inert = n !== index; });
  }
  function show(next) {
    index = (next + slides.length) % slides.length;
    update();
    viewport.scrollTo({left: index * viewport.clientWidth, behavior: motion.matches ? 'instant' : 'smooth'});
    schedule();
  }
  carousel.addEventListener('pointerenter', (event) => {
    if (event.pointerType === 'mouse') { hovered = true; schedule(); }
  });
  carousel.addEventListener('pointerleave', (event) => {
    if (event.pointerType === 'mouse') { hovered = false; schedule(); }
  });
  viewport.addEventListener('pointerdown', () => { touching = true; schedule(); });
  window.addEventListener('pointerup', () => { if (touching) { touching = false; schedule(); } });
  window.addEventListener('pointercancel', () => { touching = false; schedule(); });
  carousel.addEventListener('focusin', schedule);
  carousel.addEventListener('focusout', () => setTimeout(schedule, 0));
  viewport.addEventListener('keydown', (event) => {
    if (event.target !== viewport || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    show(index + (event.key === 'ArrowRight' ? 1 : -1));
  });
  viewport.addEventListener('scroll', () => {
    clearTimeout(timer);
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      index = Math.round(viewport.scrollLeft / viewport.clientWidth);
      update();
      schedule();
    }, 150);
  }, {passive: true});
  window.addEventListener('resize', () => {
    viewport.scrollTo({left: index * viewport.clientWidth, behavior: 'instant'});
  });
  document.addEventListener('visibilitychange', schedule);
  motion.addEventListener('change', schedule);
  update();
  schedule();
});

