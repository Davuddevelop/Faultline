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

  /* ══ the hero: the simulator's record, replayed in 3D ═══════════════
     Every vertex comes from media/sim.json via the builder: per control step
     the torso's position and orientation, each leg's body origins, the feet.
     Nothing is interpolated beyond linear blending between recorded steps. */
  var stage = document.querySelector('[data-replay]');
  var dataEl = document.getElementById('replay-data');
  if (!stage || !dataEl || !window.THREE || !motion) return;
  var T = window.THREE, D;
  try { D = JSON.parse(dataEl.textContent); } catch (e) { return; }
  var canvas = stage.querySelector('.stage__gl'), view = stage.querySelector('.stage__view');
  var renderer;
  try { renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true }); } catch (e) { return; }
  if (!renderer.getContext()) return;
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  renderer.setClearColor(0x000000, 0);

  var scene = new T.Scene();
  scene.fog = new T.Fog(0x0b0b0a, 1.7, 4.2);
  var camera = new T.PerspectiveCamera(30, 4 / 3, .01, 30);

  /* MuJoCo is z-up; three.js is y-up. (x, y, z) -> (x, z, -y) is a proper rotation. */
  function V(x, y, z) { return [x, z, -y]; }

  function mat(color, opts) { return new T.LineBasicMaterial(Object.assign({ color: color, transparent: true }, opts || {})); }
  function segGeo(capacity) {
    var g = new T.BufferGeometry();
    g.setAttribute('position', new T.BufferAttribute(new Float32Array(capacity * 6), 3));
    g.setDrawRange(0, 0);
    return g;
  }

  // ground: a drafting grid, fading out in fog
  (function () {
    var minor = [], major = [], R = 2.4, s = .1;
    for (var v = -R; v <= R + 1e-9; v += s) {
      var a = Math.abs(Math.round(v / s)) % 5 === 0 ? major : minor;
      a.push(v, 0, -R, v, 0, R, -R, 0, v, R, 0, v);
    }
    [[minor, 0x1c1c1a], [major, 0x2c2b28]].forEach(function (p) {
      var g = new T.BufferGeometry();
      g.setAttribute('position', new T.Float32BufferAttribute(p[0], 3));
      scene.add(new T.LineSegments(g, mat(p[1])));
    });
  })();

  var robotGeo = segGeo(40), robot = new T.LineSegments(robotGeo, mat(0xE9E6DE));
  var gizmoGeo = segGeo(80), gizmo = new T.LineSegments(gizmoGeo, mat(0xB5B1A8));
  var phantomGeo = segGeo(40);
  var phantom = new T.LineSegments(phantomGeo, new T.LineDashedMaterial({ color: 0x8E8B83, dashSize: .014, gapSize: .009, transparent: true }));
  var arrowGeo = segGeo(4), arrow = new T.LineSegments(arrowGeo, mat(0xE9E6DE));
  var trailGeo = new T.BufferGeometry();
  trailGeo.setAttribute('position', new T.BufferAttribute(new Float32Array(600 * 3), 3));
  trailGeo.setDrawRange(0, 0);
  var trail = new T.Line(trailGeo, mat(0x5F5D57));
  scene.add(robot, gizmo, phantom, arrow, trail);

  // joints: small rings that always face the camera
  var ring = (function () {
    var c = document.createElement('canvas'); c.width = c.height = 64;
    var x = c.getContext('2d'); x.strokeStyle = '#E9E6DE'; x.lineWidth = 7;
    x.fillStyle = '#0B0B0A'; x.beginPath(); x.arc(32, 32, 24, 0, Math.PI * 2); x.fill(); x.stroke();
    return new T.CanvasTexture(c);
  })();
  var jointGeo = new T.BufferGeometry();
  jointGeo.setAttribute('position', new T.BufferAttribute(new Float32Array(17 * 3), 3));
  var joints = new T.Points(jointGeo, new T.PointsMaterial({ size: .02, map: ring, transparent: true, alphaTest: .4, color: 0xffffff }));
  scene.add(joints);

  var HX = D.half[0], HY = D.half[1], HZ = D.half[2];
  var EDGES = [];
  (function () {
    var cs = [];
    for (var i = 0; i < 8; i++) cs.push([(i & 1) ? 1 : -1, (i & 2) ? 1 : -1, (i & 4) ? 1 : -1]);
    for (var a = 0; a < 8; a++) for (var b = a + 1; b < 8; b++) {
      var diff = 0; for (var k = 0; k < 3; k++) if (cs[a][k] !== cs[b][k]) diff++;
      if (diff === 1) EDGES.push([cs[a], cs[b]]);
    }
  })();
  function qrot(q, v) {
    var w = q[0], x = q[1], y = q[2], z = q[3];
    var tx = 2 * (y * v[2] - z * v[1]), ty = 2 * (z * v[0] - x * v[2]), tz = 2 * (x * v[1] - y * v[0]);
    return [v[0] + w * tx + y * tz - z * ty, v[1] + w * ty + z * tx - x * tz, v[2] + w * tz + x * ty - y * tx];
  }
  function frameAt(run, f) {                   // blend two recorded steps
    var F = run.f, i = Math.max(0, Math.min(F.length - 1, Math.floor(f))), j = Math.min(F.length - 1, i + 1), u = f - i;
    var a = F[i], b = F[j], r = new Array(a.length);
    for (var k = 0; k < a.length; k++) r[k] = a[k] + (b[k] - a[k]) * u;
    var qn = Math.hypot(r[3], r[4], r[5], r[6]) || 1;
    r[3] /= qn; r[4] /= qn; r[5] /= qn; r[6] /= qn;
    return r;
  }
  function tiltAt(run, f) {
    var a = run.tilt, i = Math.max(0, Math.min(a.length - 1, Math.floor(f))), j = Math.min(a.length - 1, i + 1);
    return a[i] + (a[j] - a[i]) * (f - i);
  }
  function writeRobot(geo, r) {
    var p = geo.attributes.position.array, n = 0, c = [r[0], r[1], r[2]], q = [r[3], r[4], r[5], r[6]];
    function put(m) { var t = V(m[0], m[1], m[2]); p[n++] = t[0]; p[n++] = t[1]; p[n++] = t[2]; }
    EDGES.forEach(function (e) {
      [e[0], e[1]].forEach(function (s) {
        var d = qrot(q, [s[0] * HX, s[1] * HY, s[2] * HZ]); put([c[0] + d[0], c[1] + d[1], c[2] + d[2]]);
      });
    });
    for (var leg = 0; leg < 4; leg++) {
      var o = 7 + leg * 12;
      for (var s = 0; s < 3; s++) { put(r.slice(o + s * 3, o + s * 3 + 3)); put(r.slice(o + s * 3 + 3, o + s * 3 + 6)); }
    }
    geo.attributes.position.needsUpdate = true;
    geo.setDrawRange(0, n / 3);
    return n / 3;
  }
  function writeJoints(r) {
    var p = jointGeo.attributes.position.array, n = 0;
    function put(m) { var t = V(m[0], m[1], m[2]); p[n++] = t[0]; p[n++] = t[1]; p[n++] = t[2]; }
    put([r[0], r[1], r[2]]);
    for (var leg = 0; leg < 4; leg++) { var o = 7 + leg * 12; for (var s = 0; s < 4; s++) put(r.slice(o + s * 3, o + s * 3 + 3)); }
    jointGeo.attributes.position.needsUpdate = true;
  }
  // the angle being measured: world vertical, the torso's own up-axis, the arc
  // between them, and the threshold; past it, the wedge is hatched
  function writeGizmo(r, tiltDeg) {
    var p = gizmoGeo.attributes.position.array, n = 0, c = [r[0], r[1], r[2]], q = [r[3], r[4], r[5], r[6]];
    var up = [0, 0, 1], b = qrot(q, [0, 0, 1]);
    function put(m) { var t = V(m[0], m[1], m[2]); p[n++] = t[0]; p[n++] = t[1]; p[n++] = t[2]; }
    function seg(a, d, l0, l1) { put([c[0] + d[0] * l0, c[1] + d[1] * l0, c[2] + d[2] * l0]); put([c[0] + d[0] * l1, c[1] + d[1] * l1, c[2] + d[2] * l1]); }
    var dot = Math.max(-1, Math.min(1, b[2])), ang = Math.acos(dot);
    var w = [b[0] - dot * up[0], b[1] - dot * up[1], b[2] - dot * up[2]], wl = Math.hypot(w[0], w[1], w[2]);
    if (wl < 1e-6) w = [1, 0, 0]; else w = [w[0] / wl, w[1] / wl, w[2] / wl];
    function dir(t) { return [Math.cos(t) * up[0] + Math.sin(t) * w[0], Math.cos(t) * up[1] + Math.sin(t) * w[1], Math.cos(t) * up[2] + Math.sin(t) * w[2]]; }
    for (var k = 0; k < 6; k++) seg(null, up, .05 + k * .03, .065 + k * .03);    // vertical, dashed by hand
    seg(null, b, .05, .24);                                                        // the torso's up-axis
    var thr = D.threshold * Math.PI / 180, R = .17, steps = 18;
    var lim = dir(thr); seg(null, lim, .13, .21);                                  // the limit
    for (var s = 0; s < steps; s++) {                                              // the arc of tilt
      var t0 = ang * s / steps, t1 = ang * (s + 1) / steps, d0 = dir(t0), d1 = dir(t1);
      put([c[0] + d0[0] * R, c[1] + d0[1] * R, c[2] + d0[2] * R]); put([c[0] + d1[0] * R, c[1] + d1[1] * R, c[2] + d1[2] * R]);
    }
    if (ang > thr) {                                                               // failure is hatched
      for (var h = thr + .05; h < ang && n < 80 * 6 - 6; h += .07) seg(null, dir(h), .135, .165);
    }
    gizmoGeo.attributes.position.needsUpdate = true;
    gizmoGeo.setDrawRange(0, n / 3);
  }
  function writeArrow(r, alpha) {
    var p = arrowGeo.attributes.position.array, n = 0, c = [r[0], r[1], r[2]];
    function put(m) { var t = V(m[0], m[1], m[2]); p[n++] = t[0]; p[n++] = t[1]; p[n++] = t[2]; }
    var tip = [c[0] - HX - .03, c[1], c[2]], tail = [tip[0] - .2, c[1], c[2]];
    put(tail); put(tip);
    put(tip); put([tip[0] - .035, tip[1], tip[2] + .018]);
    put(tip); put([tip[0] - .035, tip[1], tip[2] - .018]);
    arrowGeo.attributes.position.needsUpdate = true;
    arrowGeo.setDrawRange(0, n / 3);
    arrow.material.opacity = alpha;
  }

  // HUD
  var hud = {
    t: stage.querySelector('[data-hud="t"]'), tilt: stage.querySelector('[data-hud="tilt"]'),
    push: stage.querySelector('[data-hud="push"]'), bar: stage.querySelector('[data-hud="bar"]'),
    rule: stage.querySelector('[data-hud="rule"]')
  };
  var runButtons = stage.querySelectorAll('[data-run]');
  var np = stage.querySelector('[data-note-push]'), nb = stage.querySelector('[data-note-breach]');
  if (np) np.textContent = D.runs.minimal.push;
  if (nb) nb.textContent = (D.runs.minimal.tilt.findIndex(function (x) { return x > D.threshold; }) / D.hz).toFixed(2);
  var runName = 'minimal', run = D.runs[runName];
  var START = .4;                          /* the first 0.4 s is the robot settling onto the floor */
  var simT = START, hold = 0, breached = false, peak = 0, trailN = 0;
  var DUR = (run.f.length - 1) / D.hz, HOLD = 2.4;
  function reset() {
    simT = START; hold = 0; breached = false; peak = 0; trailN = 0;
    phantomGeo.setDrawRange(0, 0); trailGeo.setDrawRange(0, 0); phantomAt = null;
    hud.rule.classList.remove('is-fail');
  }
  runButtons.forEach(function (b) {
    b.addEventListener('click', function () {
      runName = b.getAttribute('data-run'); run = D.runs[runName];
      runButtons.forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); });
      reset();
    });
  });

  var target = new T.Vector3(0, .13, 0), clock = 0, phantomAt = null;
  var notes = { push: stage.querySelector('[data-note="push"]'), breach: stage.querySelector('[data-note="breach"]') };
  var pv = new T.Vector3();
  function place(el, on, at) {
    if (!el) return;
    el.classList.toggle('is-on', !!(on && at));
    if (!on || !at) return;
    var v = V(at[0], at[1], at[2]);
    pv.set(v[0], v[1], v[2]).project(camera);
    var x = (pv.x + 1) / 2 * view.clientWidth, y = (1 - pv.y) / 2 * view.clientHeight;
    el.style.transform = 'translate(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px)';
  }
  function frame(dt) {
    if (hold > 0) { hold -= dt; if (hold <= 0) reset(); }
    else { simT += dt * D.speed; if (simT >= DUR) { simT = DUR; hold = HOLD; } }
    var f = simT * D.hz, r = frameAt(run, f), tilt = tiltAt(run, f);
    peak = Math.max(peak, tilt);
    writeRobot(robotGeo, r); writeJoints(r); writeGizmo(r, tilt);

    // the torso's path, drawn as it is made
    if (hold <= 0 && trailN < 600) {
      var tp = trailGeo.attributes.position.array, v = V(r[0], r[1], r[2]);
      tp[trailN * 3] = v[0]; tp[trailN * 3 + 1] = v[1]; tp[trailN * 3 + 2] = v[2];
      trailN++; trailGeo.attributes.position.needsUpdate = true; trailGeo.setDrawRange(0, trailN);
    }
    // the push, shown around the instant it is applied
    var dtp = simT - D.push_t, show = run.push > 0 && dtp > -.35 && dtp < .3;
    writeArrow(r, show ? Math.min(1, (.3 - Math.abs(dtp + .03)) * 6) : 0);

    // at the breach, the pose is left behind in phantom line
    if (!breached && tilt > D.threshold) {
      breached = true;
      var cnt = writeRobot(phantomGeo, r);
      phantomAt = [r[0], r[1], r[2] + HZ];
      phantom.computeLineDistances(); phantomGeo.setDrawRange(0, cnt);
      hud.rule.classList.add('is-fail');
      // report the recorded control step that first exceeded the limit, not the blended frame
      var ib = run.tilt.findIndex(function (x) { return x > D.threshold; });
      hud.rule.textContent = 'tilt_deg > ' + D.threshold + ' · breached ' + (ib / D.hz).toFixed(2) + ' s';
    }
    if (!breached) hud.rule.textContent = 'tilt_deg > ' + D.threshold + ' · holds' + (simT >= DUR ? ', peak ' + peak.toFixed(2) + '°' : '');
    hud.t.textContent = simT.toFixed(2);
    hud.tilt.textContent = tilt.toFixed(2);
    hud.push.textContent = run.push > 0 ? String(run.push) : '0';
    hud.bar.style.setProperty('--w', Math.min(100, tilt / 180 * 100).toFixed(2) + '%');

    // the camera follows the torso along x and drifts slowly around it
    clock += dt;
    var tv = V(r[0], r[1], r[2]);
    target.x += (tv[0] - target.x) * Math.min(1, dt * 2.2);
    target.z += (tv[2] * .5 - target.z) * Math.min(1, dt * 2.2);
    var az = .34 + .2 * Math.sin(clock * .16), el = .3, dist = camera.aspect > 1.8 ? 1.45 : 1.35;
    camera.position.set(target.x + Math.sin(az) * Math.cos(el) * dist, target.y + Math.sin(el) * dist,
      target.z + Math.cos(az) * Math.cos(el) * dist);
    camera.lookAt(target);
    renderer.render(scene, camera);

    // drafting notes: the push where it is applied, the breach where it was left
    place(notes.push, show && arrow.material.opacity > .2, [r[0] - HX - .23, r[1], r[2]]);
    place(notes.breach, breached, phantomAt);
  }

  function resize() {
    var w = view.clientWidth, h = view.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // where the HUD sits over the view, shift the picture so the robot clears it
    if (w >= 700) camera.setViewOffset(w, h, -w * (w / h > 1.8 ? .12 : .16), h * .06, w, h); else camera.clearViewOffset();
    camera.updateProjectionMatrix();
  }
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(view);
  resize();

  var visible = true, last = null, raf = null;
  function loop(now) {
    raf = null;
    if (!visible || document.hidden) { last = null; return; }
    var dt = last === null ? 0 : Math.min(.05, (now - last) / 1000);
    last = now;
    frame(dt);
    raf = requestAnimationFrame(loop);
  }
  function kick() { if (raf === null && visible && !document.hidden) raf = requestAnimationFrame(loop); }
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (es) { visible = es[0].isIntersecting; kick(); }).observe(view);
  }
  document.addEventListener('visibilitychange', kick);
  frame(0);
  stage.classList.add('is-live', 'is-playing');
  kick();
}());
