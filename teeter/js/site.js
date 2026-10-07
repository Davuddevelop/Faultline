/* Teeter. The page reads completely without this file: every start-state
   it undoes is gated behind the .js class set before first paint, and
   nothing moves under prefers-reduced-motion. */
(function () {
  'use strict';
  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var THETA = 34.992;                         /* arctan(7 / 10), in degrees */

  /* ── the block tips to its tipping angle ──────────────── */
  var fig = document.querySelector('[data-tipfig]');
  var group = fig && fig.querySelector('.tip');
  var svg = fig && fig.querySelector('svg');
  var out = fig && fig.querySelector('[data-readout]');
  var btn = fig && fig.querySelector('[data-tip]');
  var running = false;

  function ease(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function read(a, done) {
    if (!out) return;
    out.innerHTML = 'θ = ' + a.toFixed(2) + '° <i>' +
      (done ? '· the tipping point' : '· tipping') + '</i>';
  }
  function settle() {
    group.style.transform = 'rotate(0deg)';
    svg.classList.remove('is-tipping');
    svg.querySelectorAll('.dimA').forEach(function (g) { g.style.opacity = '1'; });
    read(THETA, true);
    running = false;
  }
  function tip(delay) {
    if (!group || running) return;
    if (reduced) { settle(); return; }
    running = true;
    svg.classList.add('is-tipping');
    svg.querySelectorAll('.dimA').forEach(function (g) { g.style.opacity = ''; });
    group.style.transform = 'rotate(' + (-THETA) + 'deg)';
    read(0, false);
    var start = null, dur = 2600;
    function step(now) {
      if (start === null) start = now + (delay || 0);
      var t = Math.max(0, Math.min(1, (now - start) / dur));
      var a = THETA * ease(t);
      group.style.transform = 'rotate(' + (a - THETA).toFixed(3) + 'deg)';
      read(a, false);
      if (t < 1) requestAnimationFrame(step); else settle();
    }
    requestAnimationFrame(step);
  }
  if (group) {
    if (reduced) settle(); else tip(450);
    if (btn) btn.addEventListener('click', function () { tip(0); });
  }

  /* ── drawings scale; their lettering should not ─────────
     --k is viewBox width over rendered width, so text set at calc(11px * k)
     in the drawing's units lands on screen at 11px at any size. */
  var drawings = document.querySelectorAll('svg.fig, svg.draw');
  function fit(svgEl, width) {
    var vb = svgEl.viewBox && svgEl.viewBox.baseVal;
    if (!vb || !vb.width || !width) return;
    svgEl.style.setProperty('--k', Math.max(.5, Math.min(2.5, vb.width / width)).toFixed(3));
  }
  if ('ResizeObserver' in window) {
    var ro = new ResizeObserver(function (entries) {
      entries.forEach(function (e) { fit(e.target, e.contentRect.width); });
    });
    drawings.forEach(function (d) { ro.observe(d); });
  } else {
    drawings.forEach(function (d) { fit(d, d.getBoundingClientRect().width); });
  }

  /* ── figures play when they come into view ─────────────
     Two observers: one arms a figure (hides its start-state) while it is still
     below the fold, the other plays it once it is on screen. A figure nobody
     scrolls to is never hidden. */
  var watch = document.querySelectorAll('[data-trace],[data-reduce]');
  if ('IntersectionObserver' in window && !reduced) {
    var play = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-in');
        play.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.2 });
    var arm = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-armed');
        arm.unobserve(e.target);
        play.observe(e.target);
      });
    }, { rootMargin: '0px 0px 30% 0px' });
    watch.forEach(function (el) { arm.observe(el); });
  }

  /* ── which section you are reading ───────────────────── */
  var links = document.querySelectorAll('.mast__nav a[href^="#"]');
  if (links.length && 'IntersectionObserver' in window) {
    var byId = {};
    links.forEach(function (a) { byId[a.getAttribute('href').slice(1)] = a; });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        links.forEach(function (a) { a.classList.remove('is-here'); });
        if (byId[e.target.id]) byId[e.target.id].classList.add('is-here');
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    Object.keys(byId).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) spy.observe(el);
    });
  }
}());
