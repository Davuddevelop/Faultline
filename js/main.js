/* Faultline — scroll reveal, hero parallax, sticky nav.
   Everything here is enhancement: the page reads fine without it,
   and all of it is disabled under prefers-reduced-motion. */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── sticky nav ─────────────────────────────────────────── */
  var nav = document.getElementById('nav');
  function onScrollNav() {
    nav.classList.toggle('is-stuck', window.scrollY > 40);
  }
  onScrollNav();
  window.addEventListener('scroll', onScrollNav, { passive: true });

  /* ── reveal on enter ────────────────────────────────────── */
  var targets = document.querySelectorAll('[data-reveal]');

  if (reduced || !('IntersectionObserver' in window)) {
    targets.forEach(function (el) { el.classList.add('is-in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.12 });

    targets.forEach(function (el, i) {
      /* stagger siblings within a group so rows cascade */
      el.style.transitionDelay = (Math.min(i % 5, 4) * 70) + 'ms';
      io.observe(el);
    });
  }

  /* ── hero parallax ──────────────────────────────────────── */
  var layers = Array.prototype.slice.call(
    document.querySelectorAll('.scene [data-depth]')
  );
  var hero = document.querySelector('.hero');

  if (!reduced && layers.length && hero) {
    var ticking = false;

    function frame() {
      ticking = false;
      var y = window.scrollY;
      if (y > hero.offsetHeight) return;           /* off-screen: stop working */
      for (var i = 0; i < layers.length; i++) {
        var d = parseFloat(layers[i].getAttribute('data-depth')) || 0;
        layers[i].setAttribute('transform', 'translate(0 ' + (y * d * -1.9).toFixed(2) + ')');
      }
    }

    window.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(frame);
    }, { passive: true });
  }
})();
