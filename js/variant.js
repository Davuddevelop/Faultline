/* Shared behaviour for the landing page and its archived variants.

   Everything here is progressive: the markup reads without it, the CSS
   start-states are gated behind the .js class an inline script sets before
   first paint, and every moving part checks prefers-reduced-motion first.
   Nothing animates that isn't already a claim the page is making. */
(function () {
  'use strict';

  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var root = document.documentElement;
  var hasIO = 'IntersectionObserver' in window;

  /* ── reveal on scroll ─────────────────────────────────────── */
  /* [data-stagger] is the same mechanism with the delay pushed onto the
     children, so a table or a card row arrives in sequence rather than as
     one block. The index is set here rather than written into the markup. */
  document.querySelectorAll('[data-stagger]').forEach(function (group) {
    var kids = group.children, n = kids.length;
    for (var i = 0; i < n; i++) kids[i].style.setProperty('--i', i);
  });

  var targets = document.querySelectorAll('[data-reveal],[data-stagger],.section[data-rule]');
  if (reduced || !hasIO) {
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

  /* ── hero headline, split to words ────────────────────────── */
  /* Words, not lines: a line split has to be recomputed on every resize and
     re-run when the display face finishes loading. Words survive both, and
     each is clipped with clip-path rather than overflow so the inline
     baseline and the spacing between them are untouched. */
  function split(el) {
    var out = document.createDocumentFragment(), n = 0;

    (function walk(node, sink) {
      Array.prototype.slice.call(node.childNodes).forEach(function (child) {
        if (child.nodeType === 3) {
          child.nodeValue.split(/(\s+)/).forEach(function (piece) {
            if (!piece) return;
            if (/^\s+$/.test(piece)) { sink.appendChild(document.createTextNode(piece)); return; }
            var w = document.createElement('span'), i = document.createElement('i');
            w.className = 'w'; i.textContent = piece;
            i.style.setProperty('--i', n++);
            w.appendChild(i); sink.appendChild(w);
          });
        } else if (child.nodeType === 1) {
          var clone = child.cloneNode(false);
          walk(child, clone);
          sink.appendChild(clone);
        }
      });
    }(el, out));

    el.textContent = '';
    el.appendChild(out);
  }

  var headline = document.querySelector('[data-split]');
  if (headline && !reduced) {
    try { split(headline); } catch (err) { /* leave the heading as written */ }
  }

  /* Start the hero on the next frame so the whole sequence shares one clock
     regardless of when this script happens to run. */
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { root.classList.add('is-ready'); });
  });

  /* ── nav state and scroll progress ────────────────────────── */
  var nav = document.getElementById('nav');
  var hero = document.querySelector('[data-hero]');
  var prog = document.querySelector('[data-prog]');

  function onScroll() {
    if (nav) {
      var past = hero ? window.scrollY > hero.offsetHeight - 90 : window.scrollY > 40;
      nav.classList.toggle('is-stuck', past);
    }
    if (prog) {
      var span = document.documentElement.scrollHeight - window.innerHeight;
      var p = span > 0 ? Math.min(1, Math.max(0, window.scrollY / span)) : 0;
      prog.style.transform = 'scaleX(' + p.toFixed(4) + ')';
    }
  }

  /* ── which section you are in ─────────────────────────────── */
  /* The pills are the only navigation on the page; without this they never
     say where you already are. */
  var pills = document.querySelectorAll('.pills a[href^="#"]');
  if (pills.length && hasIO) {
    var byId = {};
    var watched = [];
    pills.forEach(function (a) {
      var el = document.getElementById(a.getAttribute('href').slice(1));
      if (!el) return;
      byId[el.id] = a;
      watched.push(el);
    });
    var current = null;
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        if (current) current.classList.remove('is-here');
        current = byId[e.target.id];
        if (current) current.classList.add('is-here');
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    watched.forEach(function (el) { spy.observe(el); });
  }

  /* ── parallax on the full-bleed photographs ───────────────── */
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
  window.addEventListener('resize', reduced ? onScroll : request, { passive: true });

  /* ── mark images done, so their placeholder can fade out ──── */
  document.querySelectorAll('img[data-fade]').forEach(function (img) {
    if (img.complete) { img.classList.add('is-loaded'); return; }
    img.addEventListener('load', function () { img.classList.add('is-loaded'); });
  });
}());
