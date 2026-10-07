/* The ink cut.

   Progressive throughout: the markup reads without this file, every CSS
   start-state is gated behind the .js class an inline script sets before
   first paint, and nothing moves when prefers-reduced-motion is set. */
(function () {
  'use strict';

  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasIO = 'IntersectionObserver' in window;

  /* ── index the things that cascade ────────────────────────── */
  document.querySelectorAll('[data-stagger]').forEach(function (group) {
    for (var i = 0; i < group.children.length; i++) {
      group.children[i].style.setProperty('--i', i);
    }
  });
  /* the scatter's 150 points, so they land in the order the search ran them */
  document.querySelectorAll('.fig__dots > circle').forEach(function (dot, i) {
    dot.style.setProperty('--i', i);
  });

  /* ── reveal ───────────────────────────────────────────────── */
  var targets = document.querySelectorAll('[data-reveal],[data-stagger],.fig-block,.sec');
  if (reduced || !hasIO) {
    targets.forEach(function (el) { el.classList.add('is-in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-in');
        io.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.06 });
    targets.forEach(function (el) { io.observe(el); });
  }

  /* ── headline, split to words ─────────────────────────────── */
  /* Words rather than lines: a line split has to be recomputed on resize
     and re-run once the serif finishes loading. Words survive both. */
  function split(el) {
    var out = document.createDocumentFragment(), n = 0;

    (function walk(node, sink) {
      Array.prototype.slice.call(node.childNodes).forEach(function (child) {
        if (child.nodeType === 3) {
          child.nodeValue.split(/(\s+)/).forEach(function (piece) {
            if (!piece) return;
            if (/^\s+$/.test(piece)) { sink.appendChild(document.createTextNode(piece)); return; }
            var w = document.createElement('span'), i = document.createElement('i');
            w.className = 'w';
            i.textContent = piece;
            i.style.setProperty('--i', n++);
            w.appendChild(i);
            sink.appendChild(w);
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

  /* One clock for the opening, whenever this file happens to run. */
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { root.classList.add('is-ready'); });
  });

  /* ── masthead: progress, and which section you are in ─────── */
  var prog = document.querySelector('[data-prog]');
  var where = document.querySelector('[data-where]');
  var sections = document.querySelectorAll('.sec[data-sec]');
  var ticking = false;

  function frame() {
    if (prog) {
      var span = root.scrollHeight - window.innerHeight;
      var p = span > 0 ? Math.min(1, Math.max(0, window.scrollY / span)) : 0;
      prog.style.transform = 'scaleX(' + p.toFixed(4) + ')';
    }
    ticking = false;
  }

  function request() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(frame);
  }

  frame();
  window.addEventListener('scroll', reduced ? frame : request, { passive: true });
  window.addEventListener('resize', request, { passive: true });

  if (where && sections.length && hasIO) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) where.textContent = e.target.getAttribute('data-sec');
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    sections.forEach(function (s) { spy.observe(s); });
  }
}());
