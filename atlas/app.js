/* Faultline — motion.
   No libraries: cdnjs is unreachable from the build sandbox, so a dependency
   could not have been verified before shipping. Everything here is testable.
   Three behaviours: Floyd–Steinberg dithering in canvas, scroll-linked
   resolve/parallax on a rAF loop, and reveals via IntersectionObserver. */
(function () {
  'use strict';
  document.documentElement.classList.add('js');
  var reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── 1. dither ─────────────────────────────────────────── */
  // Error-diffusion to 4 levels, then mapped onto the brand's two inks.
  // Done at low resolution and scaled up by the browser, so the dot grid is
  // an artefact of the arithmetic rather than a texture laid on top.
  var DEEP = [10, 22, 38], BONE = [237, 232, 220];

  function dither(canvas, img) {
    var W = 300, H = Math.max(1, Math.round(W * img.naturalHeight / img.naturalWidth));
    canvas.width = W; canvas.height = H;
    var ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, W, H);

    var d = ctx.getImageData(0, 0, W, H), p = d.data;
    var g = new Float32Array(W * H), i, x, y;
    for (i = 0; i < W * H; i++) {
      g[i] = (0.2126 * p[i * 4] + 0.7152 * p[i * 4 + 1] + 0.0722 * p[i * 4 + 2]) / 255;
    }
    var LEVELS = 3;                                   // 4 tones including black
    for (y = 0; y < H; y++) {
      for (x = 0; x < W; x++) {
        i = y * W + x;
        var old = g[i], q = Math.round(old * LEVELS) / LEVELS, err = old - q;
        g[i] = q;
        // Floyd–Steinberg: 7/16 right, 3/16 down-left, 5/16 down, 1/16 down-right
        if (x + 1 < W)            g[i + 1]     += err * 7 / 16;
        if (y + 1 < H) {
          if (x)                  g[i + W - 1] += err * 3 / 16;
                                  g[i + W]     += err * 5 / 16;
          if (x + 1 < W)          g[i + W + 1] += err * 1 / 16;
        }
      }
    }
    for (i = 0; i < W * H; i++) {
      var t = Math.min(1, Math.max(0, g[i]));
      p[i * 4]     = DEEP[0] + (BONE[0] - DEEP[0]) * t;
      p[i * 4 + 1] = DEEP[1] + (BONE[1] - DEEP[1]) * t;
      p[i * 4 + 2] = DEEP[2] + (BONE[2] - DEEP[2]) * t;
      p[i * 4 + 3] = 255;
    }
    ctx.putImageData(d, 0, 0);
  }

  [].forEach.call(document.querySelectorAll('[data-dither]'), function (cv) {
    var img = new Image();
    img.onload = function () { try { dither(cv, img); } catch (e) { cv.style.display = 'none'; } };
    img.onerror = function () { cv.style.display = 'none'; };
    img.src = cv.getAttribute('data-dither');
  });

  /* ── 2. scroll loop ────────────────────────────────────── */
  var plate   = document.querySelector('[data-plate] .plate__dither');
  var seam    = document.querySelector('.plate__seam');
  var nav     = document.querySelector('[data-nav]');
  var paras   = [].slice.call(document.querySelectorAll('[data-para]'));
  var target = 0, current = 0, ticking = false;

  function read() { target = window.scrollY || 0; }

  function frame() {
    // one-pole smoothing so the plate resolves with weight rather than snapping
    current += (target - current) * (reduced ? 1 : 0.12);
    if (Math.abs(target - current) < 0.4) current = target;

    var vh = window.innerHeight || 1;

    if (plate) {
      // fully dithered at rest, fully photographic by one screen of scroll
      var t = Math.min(1, current / (vh * 0.85));
      plate.style.opacity = String(1 - t);
      if (seam) { seam.style.transform = 'scaleY(' + (1 - t) + ')'; seam.style.opacity = String(0.5 * (1 - t)); }
    }

    if (nav) nav.classList.toggle('solid', current > vh * 0.6);

    for (var i = 0; i < paras.length; i++) {
      var el = paras[i], r = el.getBoundingClientRect();
      if (r.bottom > -200 && r.top < vh + 200) {
        var mid = (r.top + r.height / 2 - vh / 2) / vh;
        el.style.transform = 'translate3d(0,' + (mid * parseFloat(el.dataset.para) * 100).toFixed(2) + 'px,0)';
      }
    }

    if (Math.abs(target - current) > 0.4) requestAnimationFrame(frame);
    else ticking = false;
  }

  function onScroll() {
    read();
    if (!ticking) { ticking = true; requestAnimationFrame(frame); }
  }
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', onScroll, { passive: true });
  read(); current = target; frame();

  /* ── 3. reveals + counters ─────────────────────────────── */
  var rises = [].slice.call(document.querySelectorAll('[data-rise]'));
  if (!('IntersectionObserver' in window) || reduced) {
    rises.forEach(function (el) { el.classList.add('in'); });
    [].forEach.call(document.querySelectorAll('[data-count]'), function (el) {
      el.textContent = el.getAttribute('data-count');
    });
  } else {
    // stagger by position within the nearest section, so a group arrives as a group
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        var sibs = [].slice.call((el.closest('section') || document).querySelectorAll('[data-rise]'));
        el.style.transitionDelay = Math.min(sibs.indexOf(el), 6) * 70 + 'ms';
        el.classList.add('in');
        io.unobserve(el);
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.1 });
    rises.forEach(function (el) { io.observe(el); });

    var co = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target, to = parseFloat(el.getAttribute('data-count')), t0 = 0;
        function step(ts) {
          if (!t0) t0 = ts;
          var k = Math.min(1, (ts - t0) / 1100);
          el.textContent = Math.round(to * (1 - Math.pow(1 - k, 3)));
          if (k < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
        co.unobserve(el);
      });
    }, { threshold: 0.6 });
    [].forEach.call(document.querySelectorAll('[data-count]'), function (el) { co.observe(el); });
  }

  /* belt: duplicate the row so the -50% loop is seamless */
  var row = document.querySelector('[data-belt-row]');
  if (row && !reduced) row.innerHTML += row.innerHTML;
})();
