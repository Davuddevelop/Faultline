/* Teeter. The page reads completely without this file. Motion start-states
   exist only for the opening sequence (gated on .js in the stylesheet); every
   other figure is armed just before it scrolls into view, so a page that is
   never scrolled, printed or captured whole shows everything drawn. Nothing
   moves under prefers-reduced-motion. */
(function () {
  'use strict';
  var root = document.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var G = window.gsap, ST = window.ScrollTrigger;
  var motion = !!(G && ST) && !reduced && !root.classList.contains('no-motion');
  if (G && ST) G.registerPlugin(ST);
  root.classList.add('motion-ok');
  if (!motion) root.classList.add('no-motion');

  var INK = '#E9E6DE', INK3 = '#8E8B83';

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

  /* ── arm, then play ─────────────────────────────────────
     arm() hides a start-state while the element is still below the fold;
     play() runs once it is on screen. Neither runs without motion. */
  function approach(el, arm, play, start) {
    if (!motion || !el) return;
    ST.create({
      trigger: el, start: 'top bottom+=20%', once: true,
      onEnter: function () {
        arm();
        ST.create({ trigger: el, start: start || 'top 86%', once: true, onEnter: play });
      }
    });
  }

  function splitWords(el) {
    var out = [];
    (function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (n) {
        if (n.nodeType === 3) {
          var frag = document.createDocumentFragment();
          n.textContent.split(/(\s+)/).forEach(function (part) {
            if (!part) return;
            if (/^\s+$/.test(part)) { frag.appendChild(document.createTextNode(' ')); return; }
            var wm = document.createElement('span'), wi = document.createElement('span');
            wm.className = 'wm'; wi.className = 'wi'; wi.textContent = part;
            wm.appendChild(wi); frag.appendChild(wm); out.push(wi);
          });
          node.replaceChild(frag, n);
        } else if (n.nodeType === 1) { walk(n); }
      });
    })(el);
    return out;
  }

  /* ── the opening ────────────────────────────────────── */
  if (motion) {
    var tl = G.timeline({ defaults: { ease: 'expo.out' } });
    tl.fromTo('.hero [data-intro]:first-child', { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: .8 }, .1)
      .fromTo('[data-intro-line]', { yPercent: 105, y: 0 }, { yPercent: 0, y: 0, duration: 1.2, stagger: .14 }, .2)
      .fromTo('.stage', { autoAlpha: 0, y: 24 }, { autoAlpha: 1, y: 0, duration: 1.4 }, .35)
      .fromTo('.hero__text [data-intro]:not(:first-child)', { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: .9, stagger: .1 }, .6)
      .fromTo('.facts', { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: .9 }, .9);

    G.to('.mast__prog', { scaleX: 1, ease: 'none', scrollTrigger: { start: 0, end: 'max', scrub: .3 } });
  }

  /* ── headings rise, text settles in ─────────────────── */
  document.querySelectorAll('[data-rise]').forEach(function (el) {
    if (!motion) return;
    var words = splitWords(el);
    approach(el, function () { G.set(words, { yPercent: 110 }); },
      function () { G.to(words, { yPercent: 0, duration: 1, ease: 'expo.out', stagger: .025 }); });
  });
  document.querySelectorAll('[data-fade]').forEach(function (el) {
    approach(el, function () { G.set(el, { autoAlpha: 0, y: 22 }); },
      function () { G.to(el, { autoAlpha: 1, y: 0, duration: 1, ease: 'power3.out', clearProps: 'transform' }); });
  });

  /* ── statements brighten word by word as they are read ── */
  document.querySelectorAll('[data-scrub]').forEach(function (el) {
    if (!motion) return;
    var words = splitWords(el);
    G.fromTo(words, { color: INK3 }, { color: INK, ease: 'none', stagger: .08,
      scrollTrigger: { trigger: el, start: 'top 82%', end: 'bottom 48%', scrub: .5 } });
  });

  /* ── numbers count up to what the record says ───────── */
  document.querySelectorAll('[data-counts] [data-v]').forEach(function (el) {
    var end = parseInt(el.textContent, 10);
    if (isNaN(end) || String(end) !== el.textContent.trim()) return;
    var box = { v: 0 };
    approach(el, function () { el.textContent = '0'; },
      function () { G.to(box, { v: end, duration: 1.6, ease: 'power3.out',
        onUpdate: function () { el.textContent = Math.round(box.v); } }); });
  });

  /* ── coverage bars extend to what was reached ───────── */
  var spans = document.querySelectorAll('[data-cover] .axis__span');
  approach(document.querySelector('[data-cover]'),
    function () { G.set(spans, { scaleX: 0, transformOrigin: '0 50%' }); },
    function () { G.to(spans, { scaleX: 1, duration: 1.2, ease: 'expo.out', stagger: .08 }); });

  /* ── TT-103: a line runs down the stages ────────────── */
  var stages = document.querySelector('[data-stages]');
  if (stages && motion) {
    var line = document.createElement('span');
    line.className = 'stages__line';
    stages.appendChild(line);
    G.fromTo(line, { scaleY: 0 }, { scaleY: 1, ease: 'none',
      scrollTrigger: { trigger: stages, start: 'top 70%', end: 'bottom 70%', scrub: .4 } });
    stages.querySelectorAll('li').forEach(function (li) {
      ST.create({ trigger: li, start: 'top 70%', onEnter: function () { li.classList.add('is-on'); },
        onLeaveBack: function () { li.classList.remove('is-on'); } });
    });
  }

  /* ── measured traces, and the reduction, as before ──── */
  [['[data-trace]'], ['[data-reduce]']].forEach(function (sel) {
    var el = document.querySelector(sel[0]);
    approach(el, function () { el.classList.add('is-armed'); }, function () { el.classList.add('is-in'); }, 'top 80%');
  });

  /* ── TT-106: the search, replayed in the order it ran ─ */
  var search = document.querySelector('[data-search]');
  if (search) {
    var dots = Array.prototype.slice.call(search.querySelectorAll('.dots circle'));
    var zone = search.querySelectorAll('.fail-zone, .fail-edge');
    var count = search.querySelector('[data-search-count]');
    var finalCount = count ? count.innerHTML : '';
    approach(search, function () {
      G.set(dots, { autoAlpha: 0 }); G.set(zone, { autoAlpha: 0 });
      if (count) count.textContent = 'evaluation 0';
    }, function () {
      var n = dots.length, fails = 0, shown = 0;
      var t = G.timeline({ onComplete: function () { if (count) count.innerHTML = finalCount; } });
      dots.forEach(function (d, i) {
        var fail = d.getAttribute('class') === 'dot--fail', r0 = parseFloat(d.getAttribute('r'));
        t.fromTo(d, { autoAlpha: 0, attr: { r: r0 * (fail ? 3 : 2) } }, { autoAlpha: 1, attr: { r: r0 }, duration: .35, ease: 'power2.out',
          onStart: function () {
            shown = i + 1; if (fail) fails++;
            if (fail && fails === 1) G.to(zone, { autoAlpha: function (k, z) { return z.classList.contains('fail-zone') ? .55 : 1; }, duration: .6 });
            if (count) count.textContent = 'evaluation ' + shown + ' · ' + fails + ' violation' + (fails === 1 ? '' : 's');
          } }, i * (4.2 / n));
      });
    });
  }

  /* ── TT-106: every seed's line draws across the budget ─ */
  var eff = document.querySelector('[data-eff]');
  if (eff) {
    var runs = eff.querySelectorAll('.run-calm, .run-dir');
    approach(eff, function () {
      runs.forEach(function (p) { var L = p.getTotalLength(); G.set(p, { strokeDasharray: L, strokeDashoffset: L }); });
    }, function () {
      G.to(runs, { strokeDashoffset: 0, duration: 2.4, ease: 'power2.inOut', stagger: .06,
        onComplete: function () { G.set(runs, { clearProps: 'strokeDasharray,strokeDashoffset' }); } });
    });
  }

  /* ── TT-107: each pillar's drawing is drafted in ─────── */
  var pillars = document.querySelector('[data-pillars]');
  if (pillars) {
    var strokes = pillars.querySelectorAll('.pic path:not(.dash), .pic circle, .pic rect');
    var cells = pillars.querySelectorAll('li');
    approach(pillars, function () {
      strokes.forEach(function (p) { var L = p.getTotalLength(); G.set(p, { strokeDasharray: L, strokeDashoffset: L }); });
      G.set(cells, { autoAlpha: 0, y: 20 });
    }, function () {
      G.to(cells, { autoAlpha: 1, y: 0, duration: .9, ease: 'power3.out', stagger: .1 });
      G.to(strokes, { strokeDashoffset: 0, duration: 1.4, ease: 'power2.inOut', stagger: .05, delay: .2 });
    });
  }

  /* ── TT-109: the datum line runs out to the stations ── */
  var plan = document.querySelector('[data-plan]');
  if (plan && motion) {
    var datum = document.createElement('span');
    datum.className = 'plan__line';
    plan.appendChild(datum);
    var wide = window.matchMedia('(min-width: 900px)').matches;
    G.fromTo(datum, wide ? { scaleX: 0 } : { scaleY: 0 }, { scaleX: 1, scaleY: 1, ease: 'none',
      scrollTrigger: { trigger: plan, start: 'top 80%', end: 'bottom 60%', scrub: .5 } });
    var stations = plan.querySelectorAll('li');
    approach(plan, function () { G.set(stations, { autoAlpha: 0, y: 16 }); },
      function () { G.to(stations, { autoAlpha: 1, y: 0, duration: .9, ease: 'power3.out', stagger: .15 }); });
  }

  /* ── the block tips to its tipping angle ──────────────── */
  var THETA = 34.992;                          /* arctan(7 / 10), in degrees */
  var fig = document.querySelector('[data-tipfig]');
  var group = fig && fig.querySelector('.tip');
  var tsvg = fig && fig.querySelector('svg');
  var out = fig && fig.querySelector('[data-readout]');
  var btn = fig && fig.querySelector('[data-tip]');
  var tipping = false;
  function ease3(t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function read(a, done) {
    if (!out) return;
    out.innerHTML = 'θ = ' + a.toFixed(2) + '° <i>' + (done ? '· the tipping point' : '· tipping') + '</i>';
  }
  function dimA(v) { tsvg.querySelectorAll('.dimA').forEach(function (g) { g.style.opacity = v; }); }
  function upright() { group.style.transform = 'rotate(' + (-THETA) + 'deg)'; dimA('0'); read(0, false); }
  function tip(delay) {
    if (!group || tipping) return;
    tipping = true;
    upright();
    var start = null, dur = 2600;
    function step(now) {
      if (start === null) start = now + (delay || 0);
      var t = Math.max(0, Math.min(1, (now - start) / dur));
      var a = THETA * ease3(t);
      group.style.transform = 'rotate(' + (a - THETA).toFixed(3) + 'deg)';
      read(a, false);
      if (t < 1) requestAnimationFrame(step);
      else { group.style.transform = 'rotate(0deg)'; dimA('1'); read(THETA, true); tipping = false; }
    }
    requestAnimationFrame(step);
  }
  if (group) {
    approach(fig, upright, function () { tip(200); }, 'top 75%');
    if (btn) btn.addEventListener('click', function () { tip(0); });
  }

  /* ── the emblem drifts, lit; the wordmark is uncovered ─ */
  var emblem = document.querySelector('.emblem svg');
  if (emblem && motion) G.to(emblem, { rotation: 6, y: -8, duration: 4.5, ease: 'sine.inOut', yoyo: true, repeat: -1, transformOrigin: '50% 50%' });
  var wm = document.querySelector('[data-wordmark]');
  approach(wm, function () { G.set(wm, { clipPath: 'inset(0 100% 0 0)' }); },
    function () { G.to(wm, { clipPath: 'inset(0 0% 0 0)', duration: 1.8, ease: 'expo.inOut' }); }, 'top 92%');

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
    Object.keys(byId).forEach(function (id) { var el = document.getElementById(id); if (el) spy.observe(el); });
  }

  /* ══ the hero: the simulator's record, replayed in 3D (js/machine.js) ═ */
  var stage = document.querySelector('[data-replay]');
  var dataEl = document.getElementById('replay-data');
  if (!stage || !dataEl || !window.TeeterMachine || !motion) return;
  try { window.TeeterMachine.mount(stage, JSON.parse(dataEl.textContent)); } catch (e) { /* the poster stays */ }
}());
