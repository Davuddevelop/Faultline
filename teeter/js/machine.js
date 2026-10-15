/* Teeter — the machine: the simulator's record, replayed in 3D.

   Every pose comes from the record the builders write (media/sim.json, or a
   runner's replay.json): per control step the torso's position and
   orientation, each leg's body origins, the feet. Nothing is interpolated
   beyond blending between recorded steps, and nothing moves that MuJoCo did
   not move.

   It is played the way a fall is filmed. First in real time, from a tripod,
   so gravity looks like gravity; then, if a rule broke, the same seconds again
   at the record's slow rate from a side elevation, freezing on the breach and
   leaving the pose behind every tenth of a second, as a chronophotograph
   does. The rate on screen is always the rate being played.

   Used by the site's opening (js/site.js), the app's failure-mode page and the
   film (media/teeter-ad.html, which passes single: true and drives the clock).
   mount(stage, data, opts) takes a [data-replay] figure and the replay
   document, and returns a stop function, or null when WebGL is not available
   (the poster then stays). */
(function () {
  'use strict';
  function mount(stage, D, opts) {
    if (!stage || !D || !window.THREE) return null;
    opts = opts || {};
    var SINGLE = !!opts.single;              // one pass at the record's rate, on a clock the caller drives
    var T = window.THREE;
    var canvas = stage.querySelector('.stage__gl'), view = stage.querySelector('.stage__view');
    var renderer;
    try { renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true }); } catch (e) { return null; }
    if (!renderer.getContext()) return null;
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setClearColor(0x000000, 0);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = T.PCFSoftShadowMap;

    var scene = new T.Scene();
    scene.fog = new T.Fog(0x0b0b0a, 1.7, 4.2);
    var camera = new T.PerspectiveCamera(30, 4 / 3, .01, 40);

    /* MuJoCo is z-up; three.js is y-up. (x, y, z) -> (x, z, -y) is a proper rotation. */
    function V(x, y, z) { return [x, z, -y]; }

    function mat(color, o) { return new T.LineBasicMaterial(Object.assign({ color: color, transparent: true }, o || {})); }
    function segGeo(capacity) {
      var g = new T.BufferGeometry();
      g.setAttribute('position', new T.BufferAttribute(new Float32Array(capacity * 6), 3));
      g.setDrawRange(0, 0);
      return g;
    }
    function plane(m, y, order) {
      var p = new T.Mesh(new T.PlaneGeometry(12, 12), m);
      p.rotation.x = -Math.PI / 2; p.position.y = y; p.renderOrder = order;
      scene.add(p);
      return p;
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
    // the floor is drawn as nothing, but it is solid: whatever is beneath it is
    // hidden, as a floor hides it; and it takes the shadows of an overhead light
    plane(new T.MeshBasicMaterial({ colorWrite: false }), -.0006, -2);
    plane(new T.ShadowMaterial({ opacity: .6, depthWrite: false }), .0004, 1).receiveShadow = true;
    // a pool of light on the floor around the path, so the shadow has something to fall on
    var pool = (function () {
      var c = document.createElement('canvas'); c.width = c.height = 128;
      var g = c.getContext('2d'), grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
      grad.addColorStop(0, 'rgba(233,230,222,0.085)'); grad.addColorStop(.55, 'rgba(233,230,222,0.035)'); grad.addColorStop(1, 'rgba(233,230,222,0)');
      g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
      var m = new T.Mesh(new T.PlaneGeometry(1, 1), new T.MeshBasicMaterial({ map: new T.CanvasTexture(c), transparent: true, depthWrite: false }));
      m.rotation.x = -Math.PI / 2; m.position.y = .0002; m.renderOrder = 0;
      scene.add(m);
      return m;
    })();

    // a datum on the floor under the path, ticked every 0.1 m: a scale for the travel, and the
    // ground line the side elevation stands on
    var datumGeo = new T.BufferGeometry(), datum = new T.LineSegments(datumGeo, mat(0x6B6962, { depthWrite: false }));
    datum.renderOrder = 2; scene.add(datum);
    function writeDatum(x0, x1, y) {
      var p = [], a = Math.floor(x0 * 10) / 10, b = Math.ceil(x1 * 10) / 10;
      function put(m) { var t = V(m[0], m[1], m[2]); p.push(t[0], t[1], t[2]); }
      put([a, y, .0008]); put([b, y, .0008]);
      for (var k = 0, n = Math.round((b - a) * 10); k <= n; k++) { put([a + k / 10, y, .0008]); put([a + k / 10, y, k % 5 ? .008 : .016]); }
      datumGeo.setAttribute('position', new T.Float32BufferAttribute(p, 3));
    }

    // annotations are drawn over the machine, as dimensions are drawn over a part
    var gizmoGeo = segGeo(80), gizmo = new T.LineSegments(gizmoGeo, mat(0xB5B1A8, { depthTest: false }));
    var arrowGeo = segGeo(4), arrow = new T.LineSegments(arrowGeo, mat(0xE9E6DE, { depthTest: false }));
    gizmo.renderOrder = arrow.renderOrder = 10;
    var trailGeo = new T.BufferGeometry();
    trailGeo.setAttribute('position', new T.BufferAttribute(new Float32Array(600 * 3), 3));
    trailGeo.setDrawRange(0, 0);
    var trail = new T.Line(trailGeo, mat(0x5F5D57, { depthWrite: false }));
    trail.renderOrder = 4;
    // the chronophotograph: the pose every tenth of a second, older ones fainter
    var STROBE_DT = .1, STROBE_MAX = 64, STROBE_SEG = 24;
    var strobeGeo = new T.BufferGeometry();
    strobeGeo.setAttribute('position', new T.BufferAttribute(new Float32Array(STROBE_MAX * STROBE_SEG * 6), 3));
    strobeGeo.setAttribute('color', new T.BufferAttribute(new Float32Array(STROBE_MAX * STROBE_SEG * 6), 3));
    strobeGeo.setDrawRange(0, 0);
    var strobe = new T.LineSegments(strobeGeo, new T.LineBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false }));
    strobe.renderOrder = 5;
    scene.add(gizmo, arrow, trail, strobe);

    var HX = D.half[0], HY = D.half[1], HZ = D.half[2];
    function qrot(q, v) {
      var w = q[0], x = q[1], y = q[2], z = q[3];
      var tx = 2 * (y * v[2] - z * v[1]), ty = 2 * (z * v[0] - x * v[2]), tz = 2 * (x * v[1] - y * v[0]);
      return [v[0] + w * tx + y * tz - z * ty, v[1] + w * ty + z * tx - x * tz, v[2] + w * tz + x * ty - y * tx];
    }
    function frameAt(run, f) {                   // blend two recorded steps
      var F = run.f, i = Math.max(0, Math.min(F.length - 1, Math.floor(f))), j = Math.min(F.length - 1, i + 1), u = f - i;
      var a = F[i], b = F[j], r = new Array(a.length);
      var s = a[3] * b[3] + a[4] * b[4] + a[5] * b[5] + a[6] * b[6] < 0 ? -1 : 1;   // q and -q are one rotation
      for (var k = 0; k < a.length; k++) r[k] = a[k] + ((k >= 3 && k < 7 ? s * b[k] : b[k]) - a[k]) * u;
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
       collision geometry, and the caption says so; but it is kept inside the
       simulated torso box and foot spheres, so that where MuJoCo puts the robot on
       the floor, the drawing touches the floor and does not sink into it. Drawn the
       way CAD draws a part: dark shaded fill, ink outline and edges, hidden edges
       dashed. */
    var world = new T.Group();                       // works in MuJoCo's z-up frame
    world.rotation.x = -Math.PI / 2;
    scene.add(world);
    var key = new T.DirectionalLight(0xffffff, .75); key.position.set(.8, 1.6, 1.1); scene.add(key);
    scene.add(new T.HemisphereLight(0xE9E6DE, 0x0B0B0A, .5));
    // the sun that casts the shadows: overhead, a little forward, barely lighting the part
    var sun = new T.DirectionalLight(0xffffff, .06);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -.0005;
    sun.shadow.radius = 3;
    scene.add(sun, sun.target);

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
      var body = new T.Mesh(geo, fill); body.castShadow = true;
      frame.add(body, new T.Mesh(geo, OUTLINE), new T.LineSegments(edges, detail ? DETAIL : INKL), hid);
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
    function outlineOnly(frame, pts, lift) {         // a groove: drawn as edges on a face, not as a solid
      var p = [];
      for (var k = 0; k < pts.length; k++) { var a = pts[k], b = pts[(k + 1) % pts.length]; p.push(a[0], a[1], lift, b[0], b[1], lift); }
      var g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(p, 3));
      frame.add(new T.LineSegments(g, DETAIL));
    }

    // torso: shell, sensor head, tail block, deck with a recessed grip, vents, abduction motors.
    // The torso box MuJoCo collides with is 2HX x 2HY x 2HZ; the shell is inset 3 mm, and
    // the head, tail, deck and vents reach the box's faces and no further.
    var IN = .003, BV = .006, torso = frameGroup();
    solid(torso, section(chamfered(HY - BV - IN, HZ - BV - IN, .016, .008), HX * 2 - .02, BV), SHELL);
    var HEAD = .022, HEADX = HX - .006 - HEAD;      // the head's front face sits 6 mm inside the box; the lenses fill it
    solid(torso, section(chamfered(.066, .03, .012, .006), HEAD * 2 - .008, .004), DARK, false, move(HEADX, 0, .001));
    [-.026, .026].forEach(function (y) {
      solid(torso, cyl(.011, .004), METAL, false, M().multiplyMatrices(move(HX - .004, y, .006), onX()));
      solid(torso, cyl(.006, .003), DARK, true, M().multiplyMatrices(move(HX - .0015, y, .006), onX()));
    });
    solid(torso, box(.006, .07, .006), DARK, true, move(HX - .003, 0, -.014));
    solid(torso, section(chamfered(.058, .022, .008, .006), .03, .004), DARK, false, move(-HX + .019, 0, 0));
    solid(torso, box(.2, .11, .004), DARK, true, move(-.01, 0, HZ - .002));
    outlineOnly(torso, [[-.086, -.0075], [.086, -.0075], [.086, .0075], [-.086, .0075]], HZ + .0003);
    outlineOnly(torso, [[-.075, -.003], [.075, -.003], [.075, .003], [-.075, .003]], HZ + .0003);
    [-1, 1].forEach(function (side) {
      for (var v = 0; v < 6; v++) solid(torso, box(.004, .003, .026), DARK, true, move(-.05 + v * .02, side * (HY - .0015), .002));
      solid(torso, box(.07, .003, .03), DARK, true, move(.07, side * (HY - .0015), 0));
    });
    var HIPS = [[1, -1], [1, 1], [-1, -1], [-1, 1]];          // fr, fl, hr, hl, as the record orders them
    HIPS.forEach(function (h) {
      var hx = h[0] * (HX - .03), hy = h[1] * (HY - .012);
      solid(torso, cyl(.027, .05), METAL, false, M().multiplyMatrices(move(hx, hy, -.03), onX()));
      solid(torso, cyl(.019, .005), DARK, true, M().multiplyMatrices(move(hx + h[0] * .0275, hy, -.03), onX()));
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
      solid(foot, new T.IcosahedronGeometry(.019, 1), DARK);              // the foot sphere MuJoCo collides with
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
      function at(m) { var t = V(m[0], m[1], m[2]); p[n++] = t[0]; p[n++] = t[1]; p[n++] = t[2]; }
      // an annotation is drawn over the machine, but not through the floor: a segment is cut where it meets it
      function line(a, e) {
        if (a[2] < 0 && e[2] < 0) return;
        if (a[2] < 0 || e[2] < 0) {
          var u = a[2] / (a[2] - e[2]), m = [a[0] + (e[0] - a[0]) * u, a[1] + (e[1] - a[1]) * u, 0];
          if (a[2] < 0) a = m; else e = m;
        }
        at(a); at(e);
      }
      var held = null;
      function put(m) { if (held) { line(held, m); held = null; } else held = m; }
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
    // the push: along the line it acted on, through the torso, as long as the impulse is large
    function writeArrow(r, alpha, push) {
      var p = arrowGeo.attributes.position.array, n = 0, c = [r[0], r[1], r[2]];
      function put(m) { var t = V(m[0], m[1], m[2]); p[n++] = t[0]; p[n++] = t[1]; p[n++] = t[2]; }
      var len = Math.max(.06, Math.min(.34, .025 * push));
      var tip = [c[0] - HX - .03, c[1], c[2]], tail = [tip[0] - len, c[1], c[2]];
      put(tail); put(tip);
      put(tip); put([tip[0] - .035, tip[1], tip[2] + .018]);
      put(tip); put([tip[0] - .035, tip[1], tip[2] - .018]);
      arrowGeo.attributes.position.needsUpdate = true;
      arrowGeo.setDrawRange(0, n / 3);
      arrow.material.opacity = alpha;
    }
    // a strobe pose: the torso box's twelve edges and each leg's three links, exactly as recorded
    var BOXC = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]];
    var BOXE = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]];
    var strobeN = 0;
    function addStrobe(r) {
      if (strobeN >= STROBE_MAX) return;
      var p = strobeGeo.attributes.position.array, n = strobeN * STROBE_SEG * 6, q = [r[3], r[4], r[5], r[6]];
      function put(m) { var t = V(m[0], m[1], m[2]); p[n++] = t[0]; p[n++] = t[1]; p[n++] = t[2]; }
      var cs = BOXC.map(function (s) { var d = qrot(q, [s[0] * HX, s[1] * HY, s[2] * HZ]); return [r[0] + d[0], r[1] + d[1], r[2] + d[2]]; });
      BOXE.forEach(function (e) { put(cs[e[0]]); put(cs[e[1]]); });
      legs.forEach(function (L) {
        for (var k = 0; k < 3; k++) { put(r.slice(L.o + 3 * k, L.o + 3 * k + 3)); put(r.slice(L.o + 3 * k + 3, L.o + 3 * k + 6)); }
      });
      strobeN++;
      var col = strobeGeo.attributes.color.array;               // fade toward the floor's tone with age
      for (var g = 0; g < strobeN; g++) {
        var age = (strobeN - 1 - g) / Math.max(1, strobeN), v = .46 - .3 * age;
        for (var i = g * STROBE_SEG * 6; i < (g + 1) * STROBE_SEG * 6; i += 3) { col[i] = v * .91; col[i + 1] = v * .9; col[i + 2] = v * .87; }
      }
      strobeGeo.attributes.position.needsUpdate = strobeGeo.attributes.color.needsUpdate = true;
      strobeGeo.setDrawRange(0, strobeN * STROBE_SEG * 2);
    }

    // HUD
    var hud = {
      t: stage.querySelector('[data-hud="t"]'), tilt: stage.querySelector('[data-hud="tilt"]'),
      push: stage.querySelector('[data-hud="push"]'), bar: stage.querySelector('[data-hud="bar"]'),
      rule: stage.querySelector('[data-hud="rule"]')
    };
    // the rate being played, and a timeline of the run's events, under the readout
    var hudEl = stage.querySelector('.hud'), play = stage.querySelector('[data-hud="play"]');
    if (hudEl && !play) {
      play = document.createElement('div');
      play.className = 'hud__play'; play.setAttribute('data-hud', 'play');
      play.innerHTML = '<p class="hud__mode"><span data-hud="rate">1×</span><span data-hud="mode">real time</span></p>' +
        '<div class="hud__time" aria-hidden="true"><i class="hud__after"></i><i class="hud__win"></i><span class="hud__ticks"></span><i class="hud__now"></i></div>' +
        '<p class="hud__legend" data-hud="legend"></p>';
      hudEl.appendChild(play);
    }
    var tl = play && {
      rate: play.querySelector('[data-hud="rate"]'), mode: play.querySelector('[data-hud="mode"]'),
      after: play.querySelector('.hud__after'), win: play.querySelector('.hud__win'),
      ticks: play.querySelector('.hud__ticks'), now: play.querySelector('.hud__now'), legend: play.querySelector('[data-hud="legend"]')
    };
    var runButtons = stage.querySelectorAll('[data-run]');
    var np = stage.querySelector('[data-note-push]'), nb = stage.querySelector('[data-note-breach]');
    // the record keeps the push at full precision; four decimals is what any panel shows
    function num(v) { return String(+(+v).toFixed(4)); }
    function firstOver(run) { return run.tilt.findIndex(function (x) { return x > D.threshold; }); }
    if (np) np.textContent = num(D.runs.minimal.push);
    if (nb) nb.textContent = (firstOver(D.runs.minimal) / D.hz).toFixed(2);

    /* ── the cut ─────────────────────────────────────────────
       What the record says happened, and when: the push, the first control step
       past the limit, and the moment the torso comes to rest (it moves less than
       1.5 mm and turns less than 0.4° per step for 0.3 s). */
    var START = .4;                          /* the first 0.4 s is the robot settling onto the floor */
    var FREEZE = .8, HOLD = 2.4;
    var RATE = D.speed || .5;
    function eventsOf(run) {
      var F = run.f, n = F.length, hz = D.hz, ib = firstOver(run), still = Math.round(.3 * hz), rest = null;
      if (run.push > 0) {
        for (var i = Math.round(D.push_t * hz) + 3; i < n - still - 1 && rest === null; i++) {
          var ok = true;
          for (var k = i; k < i + still && ok; k++) {
            var a = F[k], b = F[k + 1];
            ok = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]) < .0015 && Math.abs(run.tilt[k + 1] - run.tilt[k]) < .4;
          }
          if (ok) rest = i / hz;
        }
      }
      return { breach: ib >= 0 ? ib / hz : null, rest: rest, end: (n - 1) / hz };
    }
    function planOf(run) {
      var E = eventsOf(run), steps = [], fell = run.push > 0 && E.breach !== null;
      if (SINGLE) {
        steps.push({ k: 'play', from: START, to: E.end, rate: RATE, mode: 'replay', cam: 'A', strobe: fell });
        steps.push({ k: 'hold', dur: HOLD });
      } else {
        var to = E.rest !== null ? Math.min(E.end, E.rest + .8) : E.end;
        steps.push({ k: 'play', from: START, to: to, rate: 1, mode: 'real time', cam: 'A' });
        if (fell) {
          steps.push({ k: 'hold', dur: .9 });
          steps.push({ k: 'dip' });
          steps.push({ k: 'play', from: Math.max(START, D.push_t - .3), to: Math.min(E.end, (E.rest !== null ? E.rest : E.end) + .3),
            rate: RATE, mode: 'replay · side elevation', cam: 'B', strobe: true, freeze: E.breach });
          steps.push({ k: 'hold', dur: 1.8 });
        } else steps.push({ k: 'hold', dur: 1.2 });
        steps.push({ k: 'dip' });
      }
      return { E: E, steps: steps };
    }

    /* ── cameras on tripods ──────────────────────────────────
       A camera that chases a falling body, or turns while it falls, adds its own
       motion to the body's. Each camera is fixed for the whole pass: it is set so
       that every point the record holds for the run, start to rest, lands inside
       the part of the stage the panels leave free. Only a drag moves it, and it
       settles back.
       A: three-quarter view. B: side elevation, on a long lens, square to the
       plane the push acts in. */
    var CAMS = { A: { az: .34, el: .3, fov: 30 }, B: { az: 0, el: .07, fov: 15 } };
    var cam = CAMS.A, aim = new T.Vector3(), ext = null, outline = [], camD = 2;

    /* Where the run may be drawn is the stylesheet's to say, at every screen size:
       the largest rectangle inside the view's --frame-inset that keeps
       --frame-gap clear of each panel laid over the view (the HUD, the tag, the
       drag hint, and whatever opts.clear names, such as a headline set over the
       stage). Largest means the one that draws the run biggest, for the shape
       the run makes on screen. opts.box, fractions of the view or a function of
       its size, overrides all of this; the film frames itself.
       What is fitted to that rectangle is the stylesheet's too, in --frame-fit:
       the box round the whole run (the default, which leaves a margin inside
       it), or 'outline', the points actually drawn over the run, which fills it. */
    var extraClear = !opts.clear ? [] : [].slice.call(typeof opts.clear === 'string' ? document.querySelectorAll(opts.clear) : opts.clear);
    var clearEls = [].slice.call(stage.querySelectorAll('.hud, .stage__tag, .stage__drag')).concat(extraClear);
    function insetOf(s, w, h) {                  // the inset shorthand, px or %, as [top, right, bottom, left] in px
      var p = String(s || '').trim().split(/\s+/).filter(Boolean);
      if (!p.length) p = ['6%'];
      function px(v, of) { var n = parseFloat(v) || 0; return /%$/.test(v) ? n / 100 * of : n; }
      return [px(p[0], h), px(p[1] || p[0], w), px(p[2] || p[0], h), px(p[3] || p[1] || p[0], w)];
    }
    function freeBox(w, h, aspect) {
      var vr = view.getBoundingClientRect(), cs = getComputedStyle(view);
      var I = insetOf(cs.getPropertyValue('--frame-inset'), w, h), g = parseFloat(cs.getPropertyValue('--frame-gap'));
      if (isNaN(g)) g = 16;
      var sx = w / (vr.width || w), sy = h / (vr.height || h);         // screen pixels to the view's own
      var A = [I[3], I[0], w - I[1], h - I[2]], obs = [], xs = [A[0], A[2]], ys = [A[1], A[3]];
      clearEls.forEach(function (el) {
        if (!el.getClientRects().length) return;                       // not shown at this size
        var r = el.getBoundingClientRect();
        var o = [(r.left - vr.left) * sx - g, (r.top - vr.top) * sy - g, (r.right - vr.left) * sx + g, (r.bottom - vr.top) * sy + g];
        if (o[2] <= A[0] || o[0] >= A[2] || o[3] <= A[1] || o[1] >= A[3]) return;   // already clear of the frame
        obs.push(o);
        [o[0], o[2]].forEach(function (x) { if (x > A[0] && x < A[2]) xs.push(x); });
        [o[1], o[3]].forEach(function (y) { if (y > A[1] && y < A[3]) ys.push(y); });
      });
      // a largest empty rectangle has each side on the frame or on a panel's edge, so those are the candidates
      var best = A, top = 0;
      for (var a = 0; a < xs.length; a++) for (var b = 0; b < xs.length; b++) {
        if (xs[b] <= xs[a]) continue;
        for (var c = 0; c < ys.length; c++) for (var d = 0; d < ys.length; d++) {
          if (ys[d] <= ys[c]) continue;
          var R = [xs[a], ys[c], xs[b], ys[d]], s = Math.min((R[2] - R[0]) / aspect, R[3] - R[1]);
          if (s <= top || obs.some(function (o) { return o[0] < R[2] && o[2] > R[0] && o[1] < R[3] && o[3] > R[1]; })) continue;
          top = s; best = R;
        }
      }
      return [best[0] / w, best[1] / h, best[2] / w, best[3] / h];
    }
    function boxOf(w, h, aspect) {
      if (typeof opts.box === 'function') return opts.box(w, h);
      if (opts.box) return opts.box;
      return freeBox(w, h, aspect);
    }
    // the run's extent in MuJoCo's frame: every torso corner and leg point recorded, the push arrow, the gizmo;
    // and its outline: the same points one by one, with where the gizmo reaches at every pose
    function frameRun(run) {
      var e = [Infinity, -Infinity, Infinity, -Infinity, 0, 0], F = run.f;
      outline = [];
      function grow(p) { e[0] = Math.min(e[0], p[0]); e[1] = Math.max(e[1], p[0]); e[2] = Math.min(e[2], p[1]); e[3] = Math.max(e[3], p[1]); e[5] = Math.max(e[5], p[2]); outline.push(p); }
      // writeGizmo draws within .24 of the torso, in the plane of the vertical and the torso's up-axis, from the
      // vertical round to the up-axis or to the limit, whichever is further, and nothing below the floor
      function reach(r) {
        var b = qrot([r[3], r[4], r[5], r[6]], [0, 0, 1]), l = Math.hypot(b[0], b[1]), u = l < 1e-6 ? [1, 0] : [b[0] / l, b[1] / l];
        var top = Math.max(Math.acos(Math.max(-1, Math.min(1, b[2]))), D.threshold * Math.PI / 180);
        for (var s = 0; s <= 8; s++) {
          var t = top * s / 8;
          outline.push([r[0] + .24 * Math.sin(t) * u[0], r[1] + .24 * Math.sin(t) * u[1], Math.max(0, r[2] + .24 * Math.cos(t))]);
        }
      }
      for (var i = Math.round(START * D.hz); i < F.length; i++) {
        var r = F[i], q = [r[3], r[4], r[5], r[6]];
        BOXC.forEach(function (c) { var d = qrot(q, [c[0] * HX, c[1] * HY, c[2] * HZ]); grow([r[0] + d[0], r[1] + d[1], r[2] + d[2]]); });
        for (var k = 7; k + 2 < r.length; k += 3) grow([r[k], r[k + 1], r[k + 2]]);
        reach(r);
      }
      if (run.push > 0) {                                      // the arrow's tail, where writeArrow puts it
        var at = F[Math.round(D.push_t * D.hz)], tail = [at[0] - HX - .03 - Math.max(.06, Math.min(.34, .025 * run.push)), at[1], at[2]];
        e[0] = Math.min(e[0], tail[0]); outline.push(tail);
      }
      e[5] = Math.max(e[5], F[0][2] + .26);                    // the gizmo stands .24 above the torso
      ext = [e[0] - .03, e[1] + .03, e[2] - .03, e[3] + .03, 0, e[5] + .02];
      writeDatum(ext[0] - .1, ext[1] + .1, (e[2] + e[3]) / 2);
      var c = V((ext[0] + ext[1]) / 2, (ext[2] + ext[3]) / 2, (ext[4] + ext[5]) / 2);
      aim.set(c[0], c[1], c[2]);
      // the shadow-casting sun stands over the middle of the travel, and lights a pool around it
      var span = Math.max(ext[1] - ext[0], ext[3] - ext[2]) + 1.1;
      pool.position.x = aim.x; pool.position.z = aim.z; pool.scale.set(span, span, 1);
      sun.target.position.set(aim.x, 0, aim.z);
      sun.position.set(aim.x + .3, 2.6, aim.z + .45);
      var sc = sun.shadow.camera, half = Math.max(ext[1] - ext[0], ext[3] - ext[2]) / 2 + .45;
      sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half; sc.near = .5; sc.far = 4.5;
      sc.updateProjectionMatrix();
      fit();
    }
    var orbit = 0, dragging = false, lastX = 0;
    view.addEventListener('pointerdown', function (e) { dragging = true; lastX = e.clientX; view.setPointerCapture(e.pointerId); });
    view.addEventListener('pointermove', function (e) { if (!dragging) return; orbit += (e.clientX - lastX) * -.006; lastX = e.clientX; });
    ['pointerup', 'pointercancel'].forEach(function (k) { view.addEventListener(k, function () { dragging = false; }); });
    function setPose(d, az) {
      camera.position.set(aim.x + Math.sin(az) * Math.cos(cam.el) * d, aim.y + Math.sin(cam.el) * d,
        aim.z + Math.cos(az) * Math.cos(cam.el) * d);
      camera.lookAt(aim);
      camera.updateMatrixWorld();
    }
    var pj = new T.Vector3(), byOutline = false;
    function projected(w, h) {                       // the screen rectangle of the extent, or of the outline, in pixels
      var r = [Infinity, Infinity, -Infinity, -Infinity];
      function add(p) {
        var m = V(p[0], p[1], p[2]);
        pj.set(m[0], m[1], m[2]).project(camera);
        var x = (pj.x + 1) / 2 * w, y = (1 - pj.y) / 2 * h;
        r[0] = Math.min(r[0], x); r[1] = Math.min(r[1], y); r[2] = Math.max(r[2], x); r[3] = Math.max(r[3], y);
      }
      if (!byOutline) {
        for (var k = 0; k < 8; k++) add([ext[k & 1 ? 1 : 0], ext[k & 2 ? 3 : 2], ext[k & 4 ? 5 : 4]]);
        return r;
      }
      outline.forEach(add);
      // the outline's points are centres: the motors, plates and feet drawn round them stand up to .035 proud
      var m = .035 * h / 2 / (camera.position.distanceTo(aim) * Math.tan(camera.fov * Math.PI / 360));
      return [r[0] - m, r[1] - m, r[2] + m, r[3] + m];
    }
    function fit() {
      var w = view.clientWidth, h = view.clientHeight;
      if (!w || !h || !ext) return;
      byOutline = getComputedStyle(view).getPropertyValue('--frame-fit').trim() === 'outline';
      camera.aspect = w / h; camera.fov = cam.fov; camera.clearViewOffset(); camera.updateProjectionMatrix();
      var d = 2, r;
      setPose(d, cam.az); r = projected(w, h);          // the run's shape on screen picks the frame
      var B = boxOf(w, h, Math.max(.25, (r[2] - r[0]) / Math.max(1, r[3] - r[1]))), bw = (B[2] - B[0]) * w, bh = (B[3] - B[1]) * h;
      for (var it = 0; it < 6; it++) {                 // a projected size falls off as 1 / distance
        setPose(d, cam.az); r = projected(w, h);
        d *= Math.max((r[2] - r[0]) / bw, (r[3] - r[1]) / bh);
      }
      setPose(d, cam.az); r = projected(w, h);
      camera.setViewOffset(w, h, (r[0] + r[2]) / 2 - (B[0] + B[2]) / 2 * w, (r[1] + r[3]) / 2 - (B[1] + B[3]) / 2 * h, w, h);
      camera.updateProjectionMatrix();
      camD = d;
      scene.fog.near = d * .92; scene.fog.far = d * 2.27;
    }
    function placeCamera(dt) {
      if (!dragging) orbit *= Math.pow(.25, dt);
      setPose(camD, cam.az + orbit);
    }

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
      // a label that would run past the frame's right edge is slid back inside it
      var sp = el.firstElementChild;
      if (sp && el.getAttribute('data-note') !== 'push') {
        var over = x + 30 + sp.offsetWidth - (view.clientWidth - 10);
        sp.style.transform = over > 0 ? 'translate(' + (30 - over).toFixed(1) + 'px,-12px)' : '';
      }
    }

    // the timeline's marks, for the run being shown
    function pct(t, E) { return (Math.max(0, Math.min(1, t / E.end)) * 100).toFixed(2) + '%'; }
    function drawTimeline(run, E) {
      if (!tl) return;
      var marks = [];
      if (run.push > 0) marks.push([D.push_t, 'push']);
      if (E.breach !== null) marks.push([E.breach, 'breach']);
      if (run.push > 0 && E.rest !== null) marks.push([E.rest, 'rest']);
      tl.ticks.innerHTML = marks.map(function (m) {
        return '<i class="hud__tick hud__tick--' + m[1] + '" style="left:' + pct(m[0], E) + '"></i>';
      }).join('');
      tl.legend.textContent = marks.length ? marks.map(function (m) { return m[1] + ' ' + m[0].toFixed(2); }).join(' · ') + ' s'
        : 'no push: ' + E.end.toFixed(1) + ' s of standing';
      tl.after.style.left = E.breach !== null ? pct(E.breach, E) : '100%';
    }

    var runName = 'minimal', run = D.runs[runName], P, si = 0, simT = START, stepT = 0, freezeLeft = 0, passDone = {};
    var breached = false, peak = 0, trailN = 0, phantomAt = null, strobeNext = null;
    function clearPass() {
      breached = false; peak = 0; trailN = 0; phantomAt = null; strobeN = 0;
      leaveGhost(false); trailGeo.setDrawRange(0, 0); strobeGeo.setDrawRange(0, 0);
      if (hud.rule) hud.rule.classList.remove('is-fail');
    }
    function begin(i) {
      si = i % P.steps.length; stepT = 0;
      var s = P.steps[si];
      if (s.k === 'play') {
        simT = s.from; freezeLeft = 0;
        if (cam !== CAMS[s.cam]) { cam = CAMS[s.cam]; fit(); }
        clearPass();
        strobeNext = s.strobe ? D.push_t : null;
        stage.setAttribute('data-pass', s.cam === 'B' ? 'replay' : 'live');
        if (tl) {
          tl.rate.textContent = (s.rate === 1 ? '1' : num(s.rate)) + '×';
          tl.mode.textContent = s.mode;
          tl.win.style.left = pct(s.from, P.E); tl.win.style.right = (100 - parseFloat(pct(s.to, P.E))).toFixed(2) + '%';
        }
      }
      if (s.k === 'dip') { canvas.style.transition = 'opacity .25s linear'; canvas.style.opacity = '0'; }
    }
    function choose(name) {
      runName = name; run = D.runs[name]; P = planOf(run);
      frameRun(run); drawTimeline(run, P.E);
      canvas.style.opacity = ''; begin(0);
    }
    runButtons.forEach(function (b) {
      b.addEventListener('click', function () {
        runButtons.forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); });
        choose(b.getAttribute('data-run'));
      });
    });

    function frame(dt) {
      var s = P.steps[si];
      if (s.k === 'play') {
        if (freezeLeft > 0) {
          freezeLeft -= dt;
          if (freezeLeft <= 0 && tl) tl.mode.textContent = s.mode;
        } else {
          var next = simT + dt * s.rate;
          if (s.freeze != null && simT < s.freeze && next >= s.freeze) {
            next = s.freeze; freezeLeft = FREEZE;
            if (tl) tl.mode.textContent = 'held at the breach';
          }
          simT = Math.min(s.to, next);
          if (simT >= s.to && freezeLeft <= 0) begin(si + 1);
        }
      } else if (s.k === 'hold') {
        stepT += dt; if (stepT >= s.dur) begin(si + 1);
      } else if (s.k === 'dip') {
        stepT += dt;
        if (stepT >= .28) { canvas.style.opacity = '1'; begin(si + 1); }
      }

      var f = simT * D.hz, r = frameAt(run, f), tilt = tiltAt(run, f);
      peak = Math.max(peak, tilt);
      pose(r); writeGizmo(r, tilt);

      // the torso's path, drawn as it is made
      if (s.k === 'play' && freezeLeft <= 0 && trailN < 600) {
        var tp = trailGeo.attributes.position.array, v = V(r[0], r[1], r[2]);
        tp[trailN * 3] = v[0]; tp[trailN * 3 + 1] = v[1]; tp[trailN * 3 + 2] = v[2];
        trailN++; trailGeo.attributes.position.needsUpdate = true; trailGeo.setDrawRange(0, trailN);
      }
      // the chronophotograph: a recorded control step every tenth of a second, from the push to rest
      var stopAt = P.E.rest !== null ? P.E.rest + STROBE_DT / 2 : P.E.end;
      while (strobeNext !== null && simT + 1e-9 >= strobeNext && strobeNext <= stopAt) {
        addStrobe(run.f[Math.min(run.f.length - 1, Math.round(strobeNext * D.hz))]);
        strobeNext += STROBE_DT;
      }
      // the push, drawn while the force acts (D.window) and a moment either side of it
      var W = D.window || .05, dtp = simT - D.push_t;
      var aA = run.push <= 0 ? 0 : dtp < -.12 ? 0 : dtp < 0 ? .45 * (dtp + .12) / .12 : dtp <= W ? 1 : dtp < W + .22 ? 1 - (dtp - W) / .22 : 0;
      writeArrow(r, aA, run.push);

      // at the breach, the pose is left behind in phantom line
      if (!breached && tilt > D.threshold) {
        breached = true;
        leaveGhost(true);
        phantomAt = [r[0], r[1], r[2] + HZ + .05];
        if (hud.rule) {
          hud.rule.classList.add('is-fail');
          // report the recorded control step that first exceeded the limit, not the blended frame
          hud.rule.textContent = 'tilt_deg > ' + D.threshold + ' · breached ' + (firstOver(run) / D.hz).toFixed(2) + ' s';
        }
      }
      var last = P.steps[si].k !== 'play';
      if (!breached && hud.rule) hud.rule.textContent = 'tilt_deg > ' + D.threshold + ' · holds' + (last ? ', peak ' + peak.toFixed(2) + '°' : '');
      if (hud.t) hud.t.textContent = simT.toFixed(2);
      if (hud.tilt) hud.tilt.textContent = tilt.toFixed(2);
      if (hud.push) hud.push.textContent = run.push > 0 ? num(run.push) : '0';
      if (hud.bar) hud.bar.style.setProperty('--w', Math.min(100, tilt / 180 * 100).toFixed(2) + '%');
      if (tl) tl.now.style.left = pct(simT, P.E);

      placeCamera(dt);
      renderer.render(scene, camera);

      // drafting notes: the push where it is applied, the breach where it was left
      place(notes.push, aA > .2, [r[0] - HX - .23, r[1], r[2]]);
      place(notes.breach, breached, phantomAt);
    }

    function resize() {
      var w = view.clientWidth, h = view.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      fit();
    }
    var ro = 'ResizeObserver' in window ? new ResizeObserver(resize) : null;
    if (ro) { ro.observe(view); extraClear.forEach(function (el) { ro.observe(el); }); }
    resize();
    // the panels' sizes settle when the fonts arrive; the HUD is not watched, since its text changes as it plays
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if (alive) fit(); });

    var visible = true, lastNow = null, raf = null;
    function loop(now) {
      raf = null;
      if (!alive || !visible || document.hidden) { lastNow = null; return; }
      var dt = lastNow === null ? 0 : Math.min(.05, (now - lastNow) / 1000);
      lastNow = now;
      frame(dt);
      raf = requestAnimationFrame(loop);
    }
    var alive = true;
    function kick() { if (alive && raf === null && visible && !document.hidden) raf = requestAnimationFrame(loop); }
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (es) { visible = es[0].isIntersecting; kick(); }) : null;
    if (io) io.observe(view);
    document.addEventListener('visibilitychange', kick);
    choose(runName);
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
      if (play && play.parentNode && !play.hasAttribute('data-static')) play.parentNode.removeChild(play);
      canvas.style.opacity = ''; canvas.style.transition = '';
      stage.removeAttribute('data-pass');
      stage.classList.remove('is-live', 'is-playing');
    };
  }
  window.TeeterMachine = { mount: mount };
}());
