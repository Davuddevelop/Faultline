/* Teeter — the machine: the simulator's record, replayed in 3D.

   Every vertex comes from media/sim.json via the builders: per control step
   the torso's position and orientation, each leg's body origins, the feet.
   Nothing is interpolated beyond linear blending between recorded steps.

   Used by the site's opening (js/site.js) and by the product prototype's
   failure-mode page (app/). mount(stage, data) takes a [data-replay] figure
   and the replay document the builder writes, and returns a stop function,
   or null when WebGL is not available (the poster then stays). */
(function () {
  'use strict';
  function mount(stage, D, opts) {
    if (!stage || !D || !window.THREE) return null;
    var OFF = opts && opts.offset;           // [x, y] fractions of the view: where to shift the picture
    var T = window.THREE;
    var canvas = stage.querySelector('.stage__gl'), view = stage.querySelector('.stage__view');
    var renderer;
    try { renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true }); } catch (e) { return null; }
    if (!renderer.getContext()) return null;
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
    // the record keeps the push at full precision; four decimals is what any panel shows
    function num(v) { return String(+(+v).toFixed(4)); }
    if (np) np.textContent = num(D.runs.minimal.push);
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
      hud.push.textContent = run.push > 0 ? num(run.push) : '0';
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
      if (OFF) camera.setViewOffset(w, h, w * OFF[0], h * OFF[1], w, h);
      else if (w >= 1000) camera.setViewOffset(w, h, -w * .2, -h * .08, w, h);
      else if (w >= 700) camera.setViewOffset(w, h, -w * .16, h * .06, w, h); else camera.clearViewOffset();
      camera.updateProjectionMatrix();
    }
    var ro = 'ResizeObserver' in window ? new ResizeObserver(resize) : null;
    if (ro) ro.observe(view);
    resize();

    var visible = true, last = null, raf = null;
    function loop(now) {
      raf = null;
      if (!alive || !visible || document.hidden) { last = null; return; }
      var dt = last === null ? 0 : Math.min(.05, (now - last) / 1000);
      last = now;
      frame(dt);
      raf = requestAnimationFrame(loop);
    }
    var alive = true;
    function kick() { if (alive && raf === null && visible && !document.hidden) raf = requestAnimationFrame(loop); }
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) { visible = es[0].isIntersecting; kick(); }) : null;
    if (io) io.observe(view);
    document.addEventListener('visibilitychange', kick);
    frame(0);
    stage.classList.add('is-live', 'is-playing');
    kick();
    // for a page that swaps views: stop the loop and let the GPU go
    return function stop() {
      alive = false;
      if (raf !== null) cancelAnimationFrame(raf);
      if (ro) ro.disconnect();
      if (io) io.disconnect();
      document.removeEventListener('visibilitychange', kick);
      renderer.dispose();
      stage.classList.remove('is-live', 'is-playing');
    };
  }
  window.TeeterMachine = { mount: mount };
}());
