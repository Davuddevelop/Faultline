/* Shared behaviour for the landing page variants:
   scroll reveals, a nav that solidifies once you leave the hero, and a
   light parallax on hero imagery. All of it defers to prefers-reduced-motion. */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── reveal on scroll ─────────────────────────────────────── */
  var targets = document.querySelectorAll('[data-reveal]');
  if (reduced || !('IntersectionObserver' in window)) {
    targets.forEach(function (el) { el.classList.add('is-in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-in');
        io.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
    targets.forEach(function (el) { io.observe(el); });
  }

  /* ── nav state ────────────────────────────────────────────── */
  var nav = document.getElementById('nav');
  var hero = document.querySelector('[data-hero]');

  function onScroll() {
    if (!nav) return;
    var past = hero ? window.scrollY > hero.offsetHeight - 90 : window.scrollY > 40;
    nav.classList.toggle('is-stuck', past);
  }

  /* ── hero parallax ────────────────────────────────────────── */
  var layers = document.querySelectorAll('[data-parallax]');
  var ticking = false;

  function frame() {
    var vh = window.innerHeight;

    layers.forEach(function (el) {
      var rate = parseFloat(el.getAttribute('data-parallax')) || 0.1;
      var host = el.parentElement;
      var r = host.getBoundingClientRect();

      /* Progress through the viewport, not absolute scrollY: -1 as the host
         enters from below, +1 as it leaves above. Using scrollY translated
         layers far down the page by hundreds of pixels and slid them out of
         frame entirely. */
      var progress = (r.top + r.height / 2 - vh / 2) / (vh / 2 + r.height / 2);
      progress = Math.max(-1, Math.min(1, progress));

      /* Never travel further than the overflow the layer actually has, or the
         bottom of the image lifts off the bottom of its container. */
      var slack = Math.max(0, el.offsetHeight - host.offsetHeight) / 2;
      var shift = -progress * Math.min(slack, vh * rate);

      el.style.transform = 'translate3d(0,' + shift.toFixed(2) + 'px,0)';
    });

    onScroll();
    ticking = false;
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(frame);
  }

  onScroll();
  window.addEventListener('scroll', reduced ? onScroll : request, { passive: true });

  /* ── mark images done, so their placeholder can fade out ──── */
  document.querySelectorAll('img[data-fade]').forEach(function (img) {
    if (img.complete) { img.classList.add('is-loaded'); return; }
    img.addEventListener('load', function () { img.classList.add('is-loaded'); });
  });
}());
