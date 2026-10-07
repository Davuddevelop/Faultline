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
      scene.add(new T.LineSegments(g, mat(p[1], { depthWrite: false })));
    });
  })();

  // annotations are drawn over the machine, as dimensions are drawn over a part
  var gizmoGeo = segGeo(80), gizmo = new T.LineSegments(gizmoGeo, mat(0xB5B1A8, { depthTest: false }));
  var arrowGeo = segGeo(4), arrow = new T.LineSegments(arrowGeo, mat(0xE9E6DE, { depthTest: false }));
  gizmo.renderOrder = arrow.renderOrder = 10;
  var trailGeo = new T.BufferGeometry();
  trailGeo.setAttribute('position', new T.BufferAttribute(new Float32Array(600 * 3), 3));
  trailGeo.setDrawRange(0, 0);
  var trail = new T.Line(trailGeo, mat(0x5F5D57, { depthWrite: false }));
  scene.add(gizmo, arrow, trail);

  var HX = D.half[0], HY = D.half[1], HZ = D.half[2];
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
  /* ── the machine ─────────────────────────────────────────
     Every pose comes from the record: the torso's position and quaternion, and
     for each leg the hip, thigh and calf body origins and the foot. The body,
     motors and links drawn around those poses are a design, not the simulated
     collision geometry, and the caption says so. Drawn the way CAD draws a part:
     dark shaded fill, ink outline and edges, hidden edges dashed. */
  var world = new T.Group();                       // works in MuJoCo's z-up frame
  world.rotation.x = -Math.PI / 2;
  scene.add(world);
  var key = new T.DirectionalLight(0xffffff, .75); key.position.set(.8, 1.6, 1.1); scene.add(key);
  scene.add(new T.HemisphereLight(0xE9E6DE, 0x0B0B0A, .5));

  function fillMat(c) { return new T.MeshLambertMaterial({ color: c, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }); }
  var SHELL = fillMat(0x1f1f1d), DARK = fillMat(0x161615), METAL = fillMat(0x2a2926);
  var INKL = new T.LineBasicMaterial({ color: 0xE9E6DE }), DETAIL = new T.LineBasicMaterial({ color: 0xA9A59C });
  var HIDDEN = new T.LineDashedMaterial({ color: 0x5F5D57, dashSize: .005, gapSize: .004, transparent: true, opacity: .85,
    depthFunc: T.GreaterDepth, depthWrite: false });
  var GHOST = new T.LineDashedMaterial({ color: 0x8E8B83, dashSize: .01, gapSize: .007, transparent: true, depthWrite: false });
  var OUTLINE = new T.MeshBasicMaterial({ color: 0xE9E6DE, side: T.BackSide });
  OUTLINE.onBeforeCompile = function (sh) {                    // an inverted hull draws the silhouette
    sh.vertexShader = sh.vertexShader.replace('#include <begin_vertex>', 'vec3 transformed = position + normal * 0.0017;');
  };
  var parts = [], ghosts = new T.Group();
  ghosts.visible = false; world.add(ghosts);

  // one solid: fill, silhouette, visible edges, hidden edges, and a ghost for the breach
  function solid(frame, geo, fill, detail, at) {
    if (at) geo.applyMatrix4(at);
    var edges = new T.EdgesGeometry(geo, 24);
    var hid = new T.LineSegments(edges, HIDDEN); hid.computeLineDistances();
    frame.add(new T.Mesh(geo, fill), new T.Mesh(geo, OUTLINE), new T.LineSegments(edges, detail ? DETAIL : INKL), hid);
    var g = new T.LineSegments(edges, GHOST); g.matrixAutoUpdate = false;
    g.userData.frame = frame; ghosts.add(g);
  }
  function frameGroup() { var g = new T.Group(); g.matrixAutoUpdate = false; world.add(g); parts.push(g); return g; }
  function M() { return new T.Matrix4(); }
  function move(x, y, z) { return M().makeTranslation(x, y, z); }
  // cylinders are built along y; turn them onto x or z as needed
  function cyl(r, len, seg) { return new T.CylinderGeometry(r, r, len, seg || 28); }
  function onX() { return M().makeRotationZ(Math.PI / 2); }
  function box(a, b, c) { return new T.BoxGeometry(a, b, c); }
  // a profile in (u, v) extruded by depth d; placed so u -> x, v -> z and the extrusion runs along y
  function plate(shape, d, bevel) {
    var g = new T.ExtrudeGeometry(shape, { depth: d, bevelEnabled: !!bevel, bevelSize: bevel || 0, bevelThickness: bevel || 0, bevelSegments: 1, curveSegments: 10 });
    g.applyMatrix4(M().set(1, 0, 0, 0, 0, 0, -1, d / 2, 0, 1, 0, 0, 0, 0, 0, 1));
    return g;
  }
  // a profile in (y, z) extruded along x by length d
  function section(shape, d, bevel) {
    var g = new T.ExtrudeGeometry(shape, { depth: d, bevelEnabled: true, bevelSize: bevel, bevelThickness: bevel, bevelSegments: 1 });
    g.applyMatrix4(M().set(0, 0, 1, -d / 2, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1));
    return g;
  }
  function chamfered(hw, hh, ct, cb) {           // half-width, half-height, top and bottom chamfers
    var sh = new T.Shape();
    sh.moveTo(-hw + cb, -hh); sh.lineTo(hw - cb, -hh); sh.lineTo(hw, -hh + cb); sh.lineTo(hw, hh - ct);
    sh.lineTo(hw - ct, hh); sh.lineTo(-hw + ct, hh); sh.lineTo(-hw, hh - ct); sh.lineTo(-hw, -hh + cb); sh.closePath();
    return sh;
  }
  // a tapered link with rounded ends from z = 0 down to z = -len, with a lightening slot
  function link(len, w0, w1, slot) {
    var sh = new T.Shape(), r0 = w0 / 2, r1 = w1 / 2;
    sh.absarc(0, 0, r0, 0, Math.PI, false);
    sh.lineTo(-r1, -len); sh.absarc(0, -len, r1, Math.PI, Math.PI * 2, false); sh.lineTo(r0, 0);
    if (slot) {
      var h = new T.Path(), a = len * .22, b = len * .78, s0 = r0 * .38, s1 = r1 * .38;
      h.absarc(0, -a, s0, 0, Math.PI, false); h.lineTo(-s1, -b); h.absarc(0, -b, s1, Math.PI, Math.PI * 2, false); h.lineTo(s0, -a);
      sh.holes.push(h);
    }
    return sh;
  }
  function boltRing(frame, n, rr, y, r) {         // bolt heads around a motor cap, on the y axis
    for (var k = 0; k < n; k++) {
      var a = k / n * Math.PI * 2;
      solid(frame, cyl(r || .0028, .003, 8), METAL, true, move(Math.cos(a) * rr, y, Math.sin(a) * rr));
    }
  }

  // torso: shell, sensor head, tail block, handle, deck plate, vents, abduction motors
  var torso = frameGroup();
  solid(torso, section(chamfered(HY + .004, HZ + .006, .016, .008), HX * 2 - .02, .006), SHELL);
  solid(torso, section(chamfered(.066, .03, .012, .006), .036, .004), DARK, false, move(HX + .016, 0, .002));
  [-.026, .026].forEach(function (y) {
    solid(torso, cyl(.011, .008), METAL, false, M().multiplyMatrices(move(HX + .04, y, .006), onX()));
    solid(torso, cyl(.006, .004), DARK, true, M().multiplyMatrices(move(HX + .046, y, .006), onX()));
  });
  solid(torso, box(.003, .07, .006), DARK, true, move(HX + .036, 0, -.014));
  solid(torso, section(chamfered(.058, .022, .008, .006), .03, .004), DARK, false, move(-HX - .012, 0, 0));
  solid(torso, box(.2, .11, .004), DARK, true, move(-.01, 0, HZ + .009));
  [-.075, .075].forEach(function (x) { solid(torso, box(.012, .012, .03), METAL, false, move(x, 0, HZ + .024)); });
  solid(torso, box(.172, .014, .01), METAL, false, move(0, 0, HZ + .042));
  [-1, 1].forEach(function (side) {
    for (var v = 0; v < 6; v++) solid(torso, box(.004, .003, .026), DARK, true, move(-.05 + v * .02, side * (HY + .0105), .002));
    solid(torso, box(.07, .003, .03), DARK, true, move(.07, side * (HY + .0105), .0));
  });
  var HIPS = [[1, -1], [1, 1], [-1, -1], [-1, 1]];          // fr, fl, hr, hl, as the record orders them
  HIPS.forEach(function (h) {
    var hx = h[0] * (HX - .03), hy = h[1] * (HY - .012);
    solid(torso, cyl(.027, .05), METAL, false, M().multiplyMatrices(move(hx, hy, -.03), onX()));
    solid(torso, cyl(.019, .006), DARK, true, M().multiplyMatrices(move(hx + h[0] * .028, hy, -.03), onX()));
  });

  // legs: hip-pitch motor at the thigh body, thigh plate, knee, shin, foot
  var F0 = D.runs.minimal.f[0];
  function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
  var legs = [0, 1, 2, 3].map(function (leg) {
    var o = 7 + leg * 12, at = function (k) { return F0.slice(o + k * 3, o + k * 3 + 3); };
    var Lt = dist(at(1), at(2)), Lc = dist(at(2), at(3)), out = leg % 2 ? 1 : -1;
    var motor = frameGroup(), thigh = frameGroup(), shin = frameGroup(), foot = frameGroup();
    // y points outward on every leg, so the outside face is +y
    // inside to outside along y: motor housing, thigh plate, motor cap and bolts
    solid(motor, cyl(.031, .034), METAL, false, move(0, -.006, 0));
    solid(motor, cyl(.023, .006), DARK, true, move(0, .028, 0));
    solid(motor, cyl(.009, .004), METAL, true, move(0, .033, 0));
    boltRing(motor, 6, .016, .0315);
    solid(thigh, plate(link(Lt, .046, .03, true), .014, .002), SHELL, false, move(0, .018, 0));
    solid(thigh, cyl(.019, .036), METAL, false, move(0, .009, -Lt));
    solid(thigh, cyl(.012, .004), DARK, true, move(0, .029, -Lt));
    solid(shin, plate(link(Lc - .012, .024, .014, true), .01, .0015), DARK, false);
    solid(shin, box(.018, .006, .05), METAL, true, move(.006, .008, -.03));
    solid(foot, new T.IcosahedronGeometry(.021, 1), DARK);
    solid(foot, cyl(.016, .008, 16), METAL, true, move(0, 0, -.004));
    return { o: o, out: out, motor: motor, thigh: thigh, shin: shin, foot: foot };
  });

  var vx = new T.Vector3(), vy = new T.Vector3(), vz = new T.Vector3();
  function basis(g, p, x, y, z) {
    vx.set(x[0], x[1], x[2]); vy.set(y[0], y[1], y[2]); vz.set(z[0], z[1], z[2]);
    g.matrix.makeBasis(vx, vy, vz).setPosition(p[0], p[1], p[2]);
    g.matrixWorldNeedsUpdate = true;
  }
  function norm(a) { var l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function sub3(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function pose(r) {
    var q = [r[3], r[4], r[5], r[6]], c = [r[0], r[1], r[2]];
    var X = qrot(q, [1, 0, 0]), Y = qrot(q, [0, 1, 0]), Z = qrot(q, [0, 0, 1]);
    basis(torso, c, X, Y, Z);
    legs.forEach(function (L) {
      var hip = r.slice(L.o, L.o + 3), th = r.slice(L.o + 3, L.o + 6), kn = r.slice(L.o + 6, L.o + 9), ft = r.slice(L.o + 9, L.o + 12);
      // the lateral axis is exact: the thigh body sits on the hip body's own y axis
      var lat = norm(sub3(th, hip)), down;
      function frameAlong(g, from, to) {
        var z = norm(sub3(from, to)), x = norm(cross(lat, z)), y = cross(z, x);
        basis(g, from, x, y, z);
      }
      down = norm(cross(cross(lat, Z), lat));
      var mx = norm(cross(lat, down));
      basis(L.motor, th, mx, lat, cross(mx, lat));
      frameAlong(L.thigh, th, kn);
      frameAlong(L.shin, kn, ft);
      var zf = norm(cross(X, lat));
      basis(L.foot, ft, cross(lat, zf), lat, zf);
    });
  }
  function leaveGhost(on) {
    ghosts.visible = on;
    if (on) ghosts.children.forEach(function (g) { g.matrix.copy(g.userData.frame.matrix); g.matrixWorldNeedsUpdate = true; });
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
    leaveGhost(false); trailGeo.setDrawRange(0, 0); phantomAt = null;
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
  // drag to orbit: the offset eases back towards the drift once let go
  var orbit = 0, dragging = false, lastX = 0;
  view.addEventListener('pointerdown', function (e) { dragging = true; lastX = e.clientX; view.setPointerCapture(e.pointerId); });
  view.addEventListener('pointermove', function (e) { if (!dragging) return; orbit += (e.clientX - lastX) * -.006; lastX = e.clientX; });
  ['pointerup', 'pointercancel'].forEach(function (k) { view.addEventListener(k, function () { dragging = false; }); });
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
    pose(r); writeGizmo(r, tilt);

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
      leaveGhost(true);
      phantomAt = [r[0], r[1], r[2] + HZ + .05];
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
    if (!dragging) orbit *= Math.pow(.35, dt);
    var az = .34 + .2 * Math.sin(clock * .16) + orbit, el = .3, dist = view.clientWidth >= 1000 ? 1.85 : (camera.aspect > 1.8 ? 1.28 : 1.55);
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
    if (w >= 1000) camera.setViewOffset(w, h, -w * .2, -h * .08, w, h);
    else if (w >= 700) camera.setViewOffset(w, h, -w * .16, h * .06, w, h); else camera.clearViewOffset();
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
