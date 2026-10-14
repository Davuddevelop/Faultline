/* Teeter — the app, live.

   When a Teeter control plane serves this page, /v1/health answers and the
   app runs against it: sign-in with a link, real campaigns planned, streamed,
   reduced and replayed, runners, programs and gates. Screens that are not
   built yet stay the prototype's, under a strip that says so. Served anywhere
   else (the static site), this file finds no API and starts the prototype.

   It uses only what js/app.js exposes as window.TeeterApp. */
(function () {
  'use strict';
  var A = window.TeeterApp;
  if (!A) return;
  var h = A.h, S = A.S, F = A.figs, esc = h.esc, $ = h.$, $$ = h.$$;
  // the prototype's own screens and hooks, put back when no control plane answers
  var PROTO = { S: Object.assign({}, S), hooks: Object.assign({}, A.hooks) };
  function prototype() {
    Object.keys(S).forEach(function (k) { if (!(k in PROTO.S)) delete S[k]; });
    Object.assign(S, PROTO.S);
    Object.assign(A.hooks, PROTO.hooks);
    A.start();
  }
  var KEY = 'teeter.token';
  var st = { me: null, programs: [], recent: [], host: location.host, methods: { link: true, workos: false, demo: null } };
  function canWrite() { return !st.me || st.me.can_write !== false; }

  /* ── the token, and the API ───────────────────────────── */
  function getToken() { try { return localStorage.getItem(KEY) || ''; } catch (e) { return ''; } }
  function setToken(t) { try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY); } catch (e) { /* private window: the session ends with the tab */ } }

  function call(method, path, body, raw) {
    var opts = { method: method, headers: { Authorization: 'Bearer ' + getToken() } };
    if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    return fetch('/v1' + path, opts).then(function (r) {
      if (r.status === 401) {
        setToken('');
        if (!/^#\/login/.test(location.hash)) h.go('/login');
        throw new Error('signed out: this token is not valid any more');
      }
      if (raw) { if (!r.ok) throw new Error('could not load ' + path + ' (' + r.status + ')'); return r; }
      if (r.status === 204) return null;
      return r.json().then(function (j) {
        if (!r.ok) throw new Error((j.error && j.error.message) || r.statusText);
        return j;
      });
    });
  }
  function get(p) { return call('GET', p); }
  function post(p, b) { return call('POST', p, b || {}); }

  /* ── pieces ────────────────────────────────────────────── */
  var FINISHED = { done: 1, failed: 1, canceled: 1 };
  function loading(what) { return '<div class="wait" style="margin-top:8px">Loading ' + esc(what || '') + '…</div>'; }
  function failure(err) {
    return h.head('TT-399', 'Something went wrong', esc(err && err.message ? err.message : String(err)), null, h.btn('Overview', { href: '/' }));
  }
  // every panel here is this workspace's own data; only prototype screens are marked
  function panel(title, inner, o) { return h.panel(title, null, inner, o || {}); }
  function count(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }
  function methodName(m) { return m === 'cem' ? 'directed (CEM)' : m === 'random' ? 'uniform' : esc(m); }
  function ckName(side) { return side.checkpoint || side.policy; }
  function progName(slug, name) {
    var pr = st.programs.filter(function (x) { return x.slug === slug; })[0];
    return pr ? pr.name : name || slug || '—';
  }
  function seconds(s) { return s < 100 ? s.toFixed(1) + ' s' : Math.round(s) + ' s'; }
  function shortPlatform(pl) {
    var m = /^(\w+)-.*?(x86_64|aarch64|arm64|amd64|i686)/.exec(pl || '');
    return m ? m[1] + ' ' + m[2] : pl || '';
  }
  function ref(c) { return '<a href="#/campaigns/' + c.ref + (FINISHED[c.state] ? '' : '/live') + '">' + c.ref + '</a>'; }
  function stateChip(s) {
    // a campaign that errored broke no rule, so it is dashed: hatching is for violations
    var map = { queued: ['setup', 'Queued'], running: ['running', 'Running'], done: ['done', 'Done'], failed: ['refused', 'Failed'],
      canceled: ['refused', 'Canceled'], passed: ['passed', 'Passed'], blocked: ['blocked', 'Blocked'], refused: ['refused', 'Refused'], waiting: ['running', 'Waiting'] };
    var m = map[s] || ['none', s];
    return h.verdict(m[0], m[1]);
  }
  function ago(iso) {
    if (!iso) return '—';
    var s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000);
    return s < 60 ? Math.round(s) + ' s ago' : s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' d ago';
  }
  function axisUnit(a) { var x = A.AX[a]; return x ? h.unit(x.unit) : ''; }
  function fmtVal(a, v) { return (typeof v === 'number' ? +v.toFixed(4) : v) + (axisUnit(a) ? ' ' + axisUnit(a) : '') + (h.REQUESTED[a] ? ' requested' : ''); }
  function wilson(k, n) {
    var z = 1.96, p = k / n, d = 1 + z * z / n, c = (p + z * z / (2 * n)) / d;
    var w = z * Math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d;
    return [Math.max(0, c - w), Math.min(1, c + w)];
  }
  function yaml(v, ind) {
    ind = ind || '';
    function scalar(x) {
      if (x === null || x === undefined) return 'null';
      if (typeof x === 'string') return /^[A-Za-z][A-Za-z0-9_.\-]*$/.test(x) && !/^(true|false|null|yes|no)$/i.test(x) ? x : JSON.stringify(x);
      return String(x);
    }
    if (Array.isArray(v)) {
      if (v.every(function (x) { return x === null || typeof x !== 'object'; })) return '[' + v.map(scalar).join(', ') + ']';
      return v.map(function (x) { return '\n' + ind + '- ' + yaml(x, ind + '  ').replace(/^\n\s*/, ''); }).join('');
    }
    if (v && typeof v === 'object') {
      return Object.keys(v).map(function (k) {
        var inner = yaml(v[k], ind + '  ');
        return '\n' + ind + k + ':' + (inner.charAt(0) === '\n' ? inner : ' ' + inner);
      }).join('');
    }
    return scalar(v);
  }
  function modal(title, inner) {
    var m = document.createElement('div');
    m.className = 'modal';
    m.innerHTML = '<div class="modal__box" role="dialog" aria-modal="true" aria-label="' + esc(title) + '"><header class="pn__h"><h2 class="pn__t">' + esc(title) + '</h2></header><div class="pn__b">' + inner + '</div></div>';
    document.body.appendChild(m);
    m.addEventListener('click', function (e) { if (e.target === m || e.target.getAttribute('data-act') === 'close') m.remove(); });
    A.cleanup.push(function () { m.remove(); });
    return m;
  }

  /* An async screen: draw a loading state, fetch, then draw — unless the
     reader has moved on to another screen in the meantime. */
  function screen(what, load, draw, after) {
    var fn = function () { return loading(what); };
    fn.after = function (p) {
      var my = A.seq();
      load(p).then(function (data) {
        if (A.seq() !== my) return;
        A.view.innerHTML = draw(data, p);
        A.refresh();
        if (after) after(data, p, my);
      }).catch(function (err) {
        if (A.seq() !== my) return;
        A.view.innerHTML = failure(err);
      });
    };
    return fn;
  }

  /* ══ screens ══════════════════════════════════════════════ */

  /* sign in */
  S.login = function () {
    return '<div class="gate-page"><aside class="hero-side" aria-hidden="true"><p class="micro">TT-301 · Teeter</p><div class="hero-side__mark">' + A.R.brand.mark2 + '</div>' +
      '<p class="hero-side__q">Robots are learning to move. We find the exact condition where they fall.</p></aside>' +
      '<div class="gate-form"><span class="gate-form__lock">' + A.R.brand.lockup + '</span>' +
      '<div><p class="micro">TT-301 · Sign in · ' + esc(st.host) + '</p><h1 class="ph__title" style="margin-top:8px">Sign in to your workspace</h1></div>' +
      (st.methods.workos ? '<a class="btn" href="/v1/auth/workos/login">Sign in</a><p class="fine">Through WorkOS, with the address your workspace invited.</p><div class="or">or with a link</div>' : '') +
      '<p class="fine">Open the sign-in link your workspace owner sent you. Each link works once.</p>' +
      '<div class="or">or paste a token</div>' +
      '<form class="f" data-form="token"><label class="f__l" for="tok">Token</label><input class="in" id="tok" type="password" placeholder="tt_usr_…" autocomplete="off" required>' +
      '<p class="f__h" data-hint>A user or CI token for this workspace. It is kept in this browser only.</p>' +
      '<button class="btn' + (st.methods.workos ? ' btn--line' : '') + '" type="submit">Sign in with the token</button></form>' +
      (st.methods.demo ? '<div class="or">or look around</div><button class="btn btn--line" type="button" data-demo>Explore ' + esc(st.methods.demo.workspace) + ', read-only</button>' +
        '<p class="fine">Real campaigns from a real runner, on a stand-in quadruped whose checkpoints hold a pose rather than run a trained policy. Read-only, for twelve hours.</p>' : '') +
      '<p class="fine" style="border-top:1px solid var(--hair);padding-top:14px">Running this server? Make a link with <code>teeter-api link --workspace &lt;slug&gt; --email &lt;address&gt;</code>.</p></div></div>';
  };
  S.login.after = function () {
    var demo = $('[data-demo]');
    if (demo) demo.addEventListener('click', function () {
      demo.disabled = true;
      fetch('/v1/auth/demo', { method: 'POST' }).then(function (r) { return r.ok ? r.json() : Promise.reject(new Error('no demo workspace here')); })
        .then(function (v) { setToken(v.token); history.replaceState(null, '', location.pathname + '#/'); boot(); })
        .catch(function (err) { demo.disabled = false; h.toast(err.message); });
    });
    var form = $('[data-form="token"]');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var t = $('#tok').value.trim();
      setToken(t);
      get('/me').then(function () { history.replaceState(null, '', location.pathname + '#/'); boot(); })
        .catch(function (err) { $('[data-hint]').textContent = 'That token did not work: ' + err.message; });
    });
  };
  S.auth = function () { return loading('your session'); };
  S.auth.after = function (p) { setToken(p.token); history.replaceState(null, '', location.pathname + '#/'); boot(); };

  /* overview */
  S.overview = screen('the workspace', function () {
    return Promise.all([get('/overview'), get('/campaigns?limit=8'), get('/runners'), get('/gates?limit=5'), get('/programs')]);
  }, function (d) {
    var ov = d[0], cs = d[1].campaigns, rs = d[2].runners, gs = d[3].gates, ps = d[4].programs;
    var running = (ov.campaigns.running || 0) + (ov.campaigns.queued || 0);
    var stats = '<div class="stats" style="margin-bottom:18px">' +
      h.stat('Runners online', ov.runners.online + '<small>/ ' + ov.runners.total + '</small>', ov.runners.total ? 'machines that dialled in during the last 90 s' : 'none yet: add one on the Runners page') +
      h.stat('Running or queued', String(running), 'campaigns') +
      h.stat('Finished', String(ov.campaigns.done || 0), (ov.campaigns.failed || 0) + ' failed') +
      h.stat('Gates', String((ov.gates.blocked || 0) + (ov.gates.passed || 0) + (ov.gates.refused || 0)), (ov.gates.blocked || 0) + ' blocked, ' + (ov.gates.passed || 0) + ' passed') + '</div>';
    var camps = cs.length ? h.table(['campaign', 'robot · policy', { t: 'evaluations', r: 1, m: 1 }, { t: 'violations', r: 1, m: 1 }, 'state', 'started'],
      cs.map(function (c) { return { href: '#/campaigns/' + c.ref + (FINISHED[c.state] ? '' : '/live'), cells: [ref(c), esc(c.robot) + ' · ' + esc(c.policy), c.evaluations + ' / ' + c.budget, String(c.failures), stateChip(c.state), ago(c.started_at || c.created_at)] }; }), { stack: true })
      : '<p class="note-line" style="padding:14px">No campaigns yet. ' + h.a('/campaigns/new', 'Plan the first one') + '.</p>';
    var runners = rs.length ? '<ul class="check">' + rs.map(function (r) { return '<li class="' + (r.online ? '' : 'is-wait') + '"><span><b>' + esc(r.name) + '</b> · ' + (r.online ? 'online' : 'last seen ' + ago(r.last_seen_at)) + ' · ' + r.cores + ' cores · MuJoCo ' + esc(r.versions.mujoco || '?') + '</span></li>'; }).join('') + '</ul>'
      : '<p class="note-line">No runner has connected. ' + h.a('/runners', 'Add one') + '; it runs on your machine and dials out, so nothing here can reach it.</p>';
    var gates = gs.length ? h.table(['gate', 'program', 'candidate · baseline', 'verdict'], gs.map(function (g) {
      return { href: '#/gates/' + g.ref, cells: ['<a href="#/gates/' + g.ref + '">' + g.ref + '</a>', esc(progName(g.program, g.program_name)), esc(ckName(g.candidate)) + ' · ' + esc(ckName(g.baseline)), stateChip(g.verdict || g.state)] };
    }), { stack: true }) : '<p class="note-line" style="padding:14px">No gates yet. Gate a checkpoint from its program.</p>';
    var progs = ps.length ? panel('Programs', h.table(['program', 'robot', 'baseline', { t: 'checkpoints', r: 1, m: 1 }], ps.map(function (pr) {
      var base = pr.checkpoints.filter(function (c) { return c.baseline; })[0];
      return { href: '#/programs/' + pr.slug, cells: ['<a href="#/programs/' + pr.slug + '">' + esc(pr.name) + '</a>', esc(pr.standard_spec.robot), base ? esc(base.label) : 'none set', String(pr.checkpoints.length)] };
    }), { stack: true }), { flush: true }) : '';
    return h.head('TT-310 · Overview', esc(st.me.workspace.name), 'Campaigns, runners and gates in this workspace.') +
      stats + (progs ? '<div class="grid" style="margin-bottom:18px">' + progs + '</div>' : '') +
      '<div class="grid grid--21">' + panel('Recent campaigns', camps, { flush: true, foot: h.a('/campaigns', 'All campaigns →') }) + panel('Runners', runners, { foot: h.a('/runners', 'Runners →') }) + '</div>' +
      '<div class="grid" style="margin-top:18px">' + panel('Recent gates', gates, { flush: true }) + '</div>';
  });

  /* campaigns */
  S.campaigns = screen('campaigns', function () { return get('/campaigns?limit=100'); }, function (d) {
    var rows = d.campaigns.map(function (c) {
      return { href: '#/campaigns/' + c.ref + (FINISHED[c.state] ? '' : '/live'), cells: [ref(c), esc(c.robot), esc(c.policy) + (c.checkpoint ? ' <span class="note-line">(' + esc(c.checkpoint) + ')</span>' : ''), methodName(c.method),
        c.evaluations + ' / ' + c.budget, String(c.failures), c.modes_found == null ? '—' : String(c.modes_found), stateChip(c.state), esc(c.runner || '—'), ago(c.created_at)] };
    });
    return h.head('TT-320 · Campaigns', 'Campaigns', 'Every search in this workspace, newest first. A violation count from a directed search describes the search, not the robot.') +
      panel(count(rows.length, 'campaign'), rows.length ? h.table(['id', 'robot', 'policy', 'method', { t: 'evaluations', r: 1, m: 1 }, { t: 'violations', r: 1, m: 1 }, { t: 'modes', r: 1, m: 1 }, 'state', 'runner', 'created'], rows, { stack: true })
        : '<p class="note-line" style="padding:14px">No campaigns yet. ' + h.a('/campaigns/new', 'Plan one') + '.</p>', { flush: true });
  });

  /* new campaign */
  var lf = null;
  function freshForm(targets) {
    var R = A.R, axes = {};
    R.axes.forEach(function (a) { var r0 = R.campaign.space[a.name]; axes[a.name] = { on: !!r0, lo: r0 ? r0[0] : 0.3, hi: r0 ? r0[1] : 0.9 }; });
    function pick(list, pref) { return list.indexOf(pref) >= 0 ? pref : list[0] || ''; }
    return { robot: pick(targets.robots, 'quadruped'), policy: pick(targets.policies, 'stand'), duration: 5.0, method: 'cem', budget: 150, reduceMax: 5, reduceBudget: 200,
      seeds: { sampler: 0, sim: 0, policy: 0 }, axes: axes,
      predicates: R.report.predicates.map(function (p) { return { name: p.name, signal: p.signal, op: p.op, threshold: p.threshold, grace_s: 0.3 }; }) };
  }
  function specOf(f) {
    var axes = {};
    A.R.axes.forEach(function (a) { var x = f.axes[a.name]; if (x.on) axes[a.name] = [+x.lo, +x.hi]; });
    return { robot: f.robot, policy: f.policy, duration_s: +f.duration, seeds: { sampler: +f.seeds.sampler, sim: +f.seeds.sim, policy: +f.seeds.policy },
      axes: axes, predicates: f.predicates.map(function (p) { return { name: p.name, signal: p.signal, op: p.op, threshold: +p.threshold, grace_s: +p.grace_s }; }),
      search: { method: f.method, budget: +f.budget, workers: -1 }, reduce: { enabled: true, max: +f.reduceMax, budget: +f.reduceBudget } };
  }
  function problems(f, targets) {
    var out = [], on = A.R.axes.filter(function (a) { return f.axes[a.name].on; });
    if (!targets.online) out.push('no runner is online to take it; it will wait in the queue');
    if (!on.length) out.push('search at least one axis');
    on.forEach(function (a) { var x = f.axes[a.name]; if (!(+x.lo < +x.hi)) out.push(a.name + ': the lower bound must be below the upper'); });
    if (!(+f.budget >= 1)) out.push('the budget must be at least 1');
    if (!f.robot || !f.policy) out.push('choose a robot and a policy a runner allows');
    return out;
  }
  S.newCampaign = screen('the runners this workspace can use', function () { return get('/runners'); }, function (d) {
    var online = d.runners.filter(function (r) { return r.online; });
    var pool = online.length ? online : d.runners;
    var targets = { robots: [], policies: [], online: online.length };
    pool.forEach(function (r) { r.robots.forEach(function (x) { if (targets.robots.indexOf(x) < 0) targets.robots.push(x); }); r.policies.forEach(function (x) { if (targets.policies.indexOf(x) < 0) targets.policies.push(x); }); });
    if (!lf || targets.robots.indexOf(lf.robot) < 0) lf = freshForm(targets);
    var f = lf;
    function options(list, cur) { return list.length ? list.map(function (x) { return '<option' + (x === cur ? ' selected' : '') + '>' + esc(x) + '</option>'; }).join('') : '<option value="">none: no runner allows one</option>'; }
    var axisRows = A.R.axes.map(function (a) {
      var x = f.axes[a.name], note = h.REQUESTED[a.name] ? 'requested ¹' : a.nominal == null ? 'relaxes to the model\'s value ²' : '';
      return { cells: ['<div class="axn"><label class="chk"><input type="checkbox" data-ax-on="' + a.name + '"' + (x.on ? ' checked' : '') + '><span class="m ink">' + a.name + '</span></label>' + (note ? '<small>' + note + '</small>' : '') + '</div>',
        '<input class="in in--sm in--num" data-ax-lo="' + a.name + '" value="' + x.lo + '" inputmode="decimal"' + (x.on ? '' : ' disabled') + '>',
        '<input class="in in--sm in--num" data-ax-hi="' + a.name + '" value="' + x.hi + '" inputmode="decimal"' + (x.on ? '' : ' disabled') + '>',
        h.unit(a.unit) || '—', String(a.tolerance)] };
    });
    var rules = f.predicates.map(function (p, i) {
      return '<div class="grid grid--4" style="align-items:end;border-top:1px solid var(--hair);padding-top:12px">' +
        '<label class="f"><span class="f__l">name</span><input class="in in--sm" data-rule="' + i + '" data-k="name" value="' + esc(p.name) + '"></label>' +
        '<label class="f"><span class="f__l">signal</span><select class="sel in--sm" data-rule="' + i + '" data-k="signal">' + A.R.signals.map(function (s) { return '<option' + (s === p.signal ? ' selected' : '') + '>' + s + '</option>'; }).join('') + '</select></label>' +
        '<label class="f"><span class="f__l">op · threshold</span><span style="display:flex;gap:6px"><select class="sel in--sm" style="width:64px" data-rule="' + i + '" data-k="op"><option' + (p.op === '>' ? ' selected' : '') + '>&gt;</option><option' + (p.op === '<' ? ' selected' : '') + '>&lt;</option></select><input class="in in--sm" data-rule="' + i + '" data-k="threshold" value="' + p.threshold + '"></span></label>' +
        '<label class="f"><span class="f__l">grace_s</span><input class="in in--sm" data-rule="' + i + '" data-k="grace_s" value="' + p.grace_s + '"></label>' +
        '<p class="note-line" style="grid-column:1/-1" data-sentence="' + i + '">' + h.ruleSentence(p, p.grace_s) + '</p></div>';
    }).join('');
    var who = online.length ? count(online.length, 'runner') + ' online: ' + online.map(function (r) { return esc(r.name); }).join(', ')
      : d.runners.length ? 'No runner is online. The campaign will wait in the queue until one connects.' : 'No runner has ever connected. ' + h.a('/runners', 'Add one') + ' first.';
    return h.head('TT-321 · New campaign', 'Plan a campaign', 'The space, the rules and the search, in real units. Robots and policies are the ones your runners allow; the server cannot name anything else.', '<span>' + who + '</span>') +
      '<div class="grid--form"><div class="grid">' +
      panel('1 · Robot and policy', '<div class="grid grid--3"><label class="f"><span class="f__l">Robot</span><select class="sel" data-f="robot">' + options(targets.robots, f.robot) + '</select></label>' +
        '<label class="f"><span class="f__l">Policy</span><select class="sel" data-f="policy">' + options(targets.policies, f.policy) + '</select></label>' +
        '<label class="f"><span class="f__l">Duration per run, s</span><input class="in" data-f="duration" value="' + f.duration + '"></label></div>' +
        '<p class="note-line">Names come from the runners\' allowlists (their <code>runner.yaml</code>). The runner resolves each to a file on its own disk.</p>') +
      panel('2 · Space', h.table(['axis', { t: 'from', m: 1 }, { t: 'to', m: 1 }, 'unit', { t: 'tolerance', m: 1 }], axisRows, { stack: true }) +
        '<p class="note-line">¹ Applied on the ' + 50 + ' Hz control grid, so the robot receives a quantised value: the record says requested. ² Reduction relaxes friction toward the model\'s own value, not toward zero. Tolerance is how finely reduction resolves each axis.</p>') +
      panel('3 · Rules', rules + '<p class="note-line">A rule sees only the four recorded signals: ' + A.R.signals.map(function (s) { return '<code>' + s + '</code>'; }).join(', ') + '.</p>') +
      panel('4 · Search', '<div class="f"><span class="f__l">Method</span><div class="seg seg--wide" role="group" aria-label="Method"><button type="button" data-method="cem" aria-pressed="' + (f.method === 'cem') + '">Directed · CEM</button><button type="button" data-method="random" aria-pressed="' + (f.method === 'random') + '">Uniform · random</button></div></div>' +
        '<div class="grid grid--3" style="align-items:end"><label class="f"><span class="f__l">Budget</span><input class="in" data-f="budget" value="' + f.budget + '" inputmode="numeric"></label>' +
        '<label class="f"><span class="f__l">Reduce, most severe</span><input class="in" data-f="reduceMax" value="' + f.reduceMax + '" inputmode="numeric"></label>' +
        '<label class="f"><span class="f__l">Sampler seed</span><input class="in" data-seed="sampler" value="' + f.seeds.sampler + '"></label></div>' +
        '<p class="note-line" data-method-note></p>') + '</div>' +
      '<div class="grid sticky" style="position:sticky;top:110px">' + panel('Campaign spec · teeter.campaign/1', '<pre class="code" data-yaml style="max-height:52vh"></pre><p class="note-line">Saved as <code>spec.yaml</code>, it runs from a terminal too: <code>teeter campaign run spec.yaml</code>.</p>', { act: '<button class="copy__b" style="position:static" type="button" data-copy-yaml>Copy</button>' }) +
      panel('Checks', '<ul class="check" data-checks></ul><div class="acts">' + h.btn('Start campaign', { act: 'start' }) + h.btn('Reset', { act: 'reset', line: true }) + '</div><p class="note-line" data-start-error></p>') + '</div></div>';
  }, function (d, p, my) {
    var online = d.runners.filter(function (r) { return r.online; }).length;
    var targets = { online: online };
    function refreshForm() {
      var spec = specOf(lf), probs = problems(lf, targets);
      $('[data-yaml]').textContent = yaml(spec).replace(/^\n/, '');
      $('[data-checks]').innerHTML = (probs.length ? probs.map(function (x) { return '<li class="' + (/queue/.test(x) ? 'is-warn' : 'is-no') + '">' + esc(x) + '</li>'; }).join('') : '<li>valid against teeter.campaign/1; the server checks it again</li>') +
        '<li class="is-warn">' + (lf.method === 'cem' ? 'directed search: its violation count will describe the search, not a failure rate' : 'uniform sampling: supports a failure rate with an interval, over the declared box only') + '</li>';
      $('[data-method-note]').textContent = lf.method === 'cem' ? 'CEM concentrates its budget where violations are dense.' : 'Uniform sampling spends the budget evenly; only it supports a rate.';
      $('[data-act="start"]').disabled = probs.some(function (x) { return !/queue/.test(x); });
      lf.predicates.forEach(function (q, i) { var el = $('[data-sentence="' + i + '"]'); if (el) el.innerHTML = h.ruleSentence(q, +q.grace_s); });
    }
    function onInput(e) {
      var t = e.target, k;
      if ((k = t.getAttribute('data-ax-on'))) { lf.axes[k].on = t.checked; $('[data-ax-lo="' + k + '"]').disabled = $('[data-ax-hi="' + k + '"]').disabled = !t.checked; }
      else if ((k = t.getAttribute('data-ax-lo'))) lf.axes[k].lo = t.value;
      else if ((k = t.getAttribute('data-ax-hi'))) lf.axes[k].hi = t.value;
      else if (t.hasAttribute('data-rule')) lf.predicates[+t.getAttribute('data-rule')][t.getAttribute('data-k')] = t.value;
      else if ((k = t.getAttribute('data-seed'))) lf.seeds[k] = t.value;
      else if ((k = t.getAttribute('data-f'))) lf[k] = t.value;
      refreshForm();
    }
    A.view.addEventListener('input', onInput);
    A.view.addEventListener('change', onInput);
    A.cleanup.push(function () { A.view.removeEventListener('input', onInput); A.view.removeEventListener('change', onInput); });
    $$('[data-method]').forEach(function (b) { b.addEventListener('click', function () { lf.method = b.getAttribute('data-method'); $$('[data-method]').forEach(function (o) { o.setAttribute('aria-pressed', String(o === b)); }); refreshForm(); }); });
    $('[data-act="reset"]').addEventListener('click', function () { lf = null; A.render(); });
    $('[data-copy-yaml]').addEventListener('click', function () { h.copyText(yaml(specOf(lf)).replace(/^\n/, '') + '\n'); });
    $('[data-act="start"]').addEventListener('click', function () {
      var b = $('[data-act="start"]');
      b.disabled = true; b.textContent = 'Queuing…';
      post('/campaigns', { spec: specOf(lf) }).then(function (c) { h.toast(c.ref + ' queued'); h.go('/campaigns/' + c.ref + '/live'); })
        .catch(function (err) { b.disabled = false; b.textContent = 'Start campaign'; $('[data-start-error]').textContent = err.message; });
    });
    refreshForm();
  });


  // a read-only member or a demo visitor gets an explanation, not the form
  var planScreen = S.newCampaign;
  S.newCampaign = function (p) {
    return canWrite() ? planScreen(p) : h.head('TT-322 · New campaign', 'This visit is read-only',
      'You can open every campaign, failure mode, replay and gate in ' + esc(st.me.workspace.name) + ', but not plan new ones. Planning needs a member who is not a viewer.',
      null, h.btn('Campaigns', { href: '/campaigns' }));
  };
  S.newCampaign.after = function (p) { if (canWrite()) planScreen.after(p); };
  /* live run */
  var SHORT = { push_impulse_ns: 'push', slope_deg: 'slope', sensor_lag_ms: 'lag', torque_loss_pct: 'torque', payload_kg: 'load', payload_offset_m: 'offset', friction_mu: 'mu' };
  function axesOf(spec) { return Object.keys(spec.axes); }
  function point(spec, e) {
    var ax = axesOf(spec), x = e.perturbation[ax[0]];
    var y = ax[1] ? e.perturbation[ax[1]] : Math.max(-60, Math.min(60, e.severity == null ? -60 : e.severity));
    return { x: x, y: y, f: e.failed, invalid: !!e.invalid };
  }
  function scatterFor(spec, pts) {
    var ax = axesOf(spec);
    return F.scatter({ points: pts, xAxis: ax[0], yAxis: ax[1] || 'severity', xb: spec.axes[ax[0]], yb: ax[1] ? spec.axes[ax[1]] : [-60, 60],
      xUnit: axisUnit(ax[0]), yUnit: ax[1] ? axisUnit(ax[1]) : 'signed margin', xRequested: !!h.REQUESTED[ax[0]] });
  }
  function phaseText(c) {
    var p = c.progress || {};
    if (c.state === 'queued') return p.last_error ? 'waiting for a runner (last attempt: ' + p.last_error + ')' : 'waiting for a runner';
    if (p.phase === 'reduce') return 'reducing ' + (p.reduced || 0) + ' of ' + (p.to_reduce || '?') + ' most severe failures';
    if (p.phase === 'capture') return 'recording replays, ' + (p.captured || 0) + ' of ' + (p.to_capture || 0);
    if (p.phase === 'upload') return 'uploading the result';
    if (p.phase === 'search') return 'searching';
    return c.state;
  }
  S.live = screen('the campaign', function (p) { return get('/campaigns/' + p.id); }, function (c) {
    var ax = axesOf(c.spec);
    return h.head('TT-322 · Live run', c.ref + ' · <span data-l="title">' + esc(c.state) + '</span>', 'Each evaluation lands here as the runner measures it. ' + esc(c.robot) + ' · ' + esc(c.policy) + ' · ' + methodName(c.method) + ', ' + c.budget + ' evaluations.',
      '<span data-l="phase">' + esc(phaseText(c)) + '</span><span>runner <b data-l="runner">' + esc(c.runner || '—') + '</b></span>',
      FINISHED[c.state] ? '' : h.btn('Cancel', { act: 'cancel', line: true })) +
      '<div class="stats" style="margin-bottom:18px">' + h.stat('Evaluations', '<span data-l="n">' + c.evaluations + '</span><small>/ ' + c.budget + '</small>') +
      h.stat('Violations', '<span data-l="k">' + c.failures + '</span>', c.method === 'cem' ? 'of directed evaluations; describes the search' : 'of uniform samples') +
      h.stat('First violation', '<span data-l="first">' + (c.first_failure_index == null ? '—' : c.first_failure_index) + '</span>', 'evaluations spent before it') +
      h.stat('Elapsed', '<span data-l="t">—</span>', 'wall time on the runner') + '</div>' +
      '<div class="prog-bar" data-l="bar" style="margin-bottom:18px"><i></i><b></b></div>' +
      '<div data-l="done"></div>' +
      '<div class="grid grid--21">' + panel('Where the evaluations land · ' + (ax[1] ? ax[0] + ' against ' + ax[1] : ax[0] + ' against severity'), '<div data-l="scatter">' + scatterFor(c.spec, []) + '</div>') +
      panel('Runner log', '<div class="log" data-l="log" aria-live="off"></div>', { flush: true, cls: 'pn--log', foot: 'Each line is one evaluation as stored: the two plotted axes, requested, and whether a rule fired. Hover a line for every axis.' }) + '</div>';
  }, function (c, p, my) {
    var pts = [], after = -1, bar = $('[data-l="bar"]'), log = $('[data-l="log"]');
    var ax = axesOf(c.spec), budget = c.budget, started = c.started_at ? Date.parse(c.started_at) : null;
    // a finished campaign shows the server's own duration, the figure its result page quotes
    var dur = c.duration_s == null ? null : c.duration_s;
    function elapsed() {
      var el = $('[data-l="t"]');
      if (dur != null) el.textContent = seconds(dur);
      else if (started) el.textContent = seconds((Date.now() - started) / 1000);
    }
    var cancel = $('[data-act="cancel"]');
    if (cancel) cancel.addEventListener('click', function () {
      post('/campaigns/' + c.ref + '/cancel').then(function () { h.toast('Cancel requested; the runner stops at its next heartbeat'); }).catch(function (e) { h.toast(e.message); });
    });
    function line(e) {
      var div = document.createElement('div');
      div.className = e.failed ? 'is-fail' : '';
      div.textContent = '#' + String(e.index + 1).padStart(4, '0') + '  ' + ax.slice(0, 2).map(function (a) { return SHORT[a] + ' ' + (+e.perturbation[a]).toFixed(2); }).join('  ') + (ax.length > 2 ? '  +' + (ax.length - 2) : '') + '  ' + (e.invalid ? 'invalid' : e.failed ? 'violated' : 'held');
      div.title = ax.map(function (a) { return a + ' ' + e.perturbation[a]; }).join(', ') + (e.violation ? '; ' + e.violation.predicate + ' at ' + e.violation.first_t + ' s' : '');
      return div;
    }
    function tick() {
      get('/campaigns/' + c.ref + '/evaluations?after=' + after + '&limit=2000').then(function (pg) {
        if (A.seq() !== my) return;
        pts.forEach(function (q) { q.fresh = false; });
        var frag = document.createDocumentFragment();
        pg.evaluations.forEach(function (e) { var q = point(c.spec, e); q.fresh = true; pts.push(q); frag.appendChild(line(e)); });
        if (pg.evaluations.length) {
          log.appendChild(frag); log.scrollTop = log.scrollHeight;
          $('[data-l="scatter"]').innerHTML = scatterFor(c.spec, pts); A.refresh();
        }
        after = pg.next_after;
        $('[data-l="n"]').textContent = pg.evaluations_total;
        $('[data-l="k"]').textContent = pg.failures_total;
        $('[data-l="first"]').textContent = pg.first_failure_index == null ? '—' : pg.first_failure_index;
        bar.querySelector('i').style.width = (pg.evaluations_total / budget * 100) + '%';
        if (pg.first_failure_index != null) { bar.classList.add('has-m'); bar.style.setProperty('--m', (pg.first_failure_index / budget * 100) + '%'); }
        $('[data-l="title"]').textContent = pg.state;
        $('[data-l="phase"]').textContent = phaseText({ state: pg.state, progress: pg.progress });
        elapsed();
        if (FINISHED[pg.state]) {
          var cb = $('[data-act="cancel"]');
          if (cb) cb.remove();
          get('/campaigns/' + c.ref).then(function (full) {
            if (A.seq() !== my) return;
            var ok = full.state === 'done';
            if (full.duration_s != null) { dur = full.duration_s; elapsed(); }
            $('[data-l="done"]').innerHTML = '<div class="banner' + (ok && full.modes.length ? ' banner--inv' : '') + '" style="margin-bottom:18px">' + (ok && full.modes.length ? '<span class="banner__sw" aria-hidden="true"></span>' : '') +
              '<div class="banner__body"><p class="banner__t">' + (ok ? (full.modes.length ? full.modes.length + ' failure mode' + (full.modes.length > 1 ? 's' : '') + ' found' : 'No violations found') : 'Campaign ' + full.state) + '</p>' +
              '<p class="banner__d">' + (ok ? (full.modes.length ? 'Reduced, grouped and replayed on ' + esc(full.runner) + '. Found in simulation, MuJoCo ' + esc(full.result.environment.mujoco) + '.' : 'That bounds nothing: this budget, in this space, did not find one.') : esc(full.error || '')) + '</p></div>' +
              h.btn('Open result', { href: '/campaigns/' + c.ref }) + '</div>';
            A.refresh();
          });
          return;
        }
        if (!started && pg.state === 'running') get('/campaigns/' + c.ref).then(function (x) { started = x.started_at ? Date.parse(x.started_at) : null; $('[data-l="runner"]').textContent = x.runner || '—'; });
        A.later(tick, 1000);
      }).catch(function () { if (A.seq() === my) A.later(tick, 3000); });
    }
    tick();
  });

  /* campaign result */
  S.campaign = screen('the campaign', function (p) {
    return get('/campaigns/' + p.id).then(function (c) {
      return FINISHED[c.state] ? get('/campaigns/' + p.id + '/evaluations?limit=5000').then(function (pg) { c._evs = pg.evaluations; return c; }) : c;
    });
  }, function (c) {
    var meta = '<span>' + esc(c.robot) + ' · ' + esc(c.policy) + '</span><span>' + methodName(c.method) + ' · seed ' + c.spec.seeds.sampler + '</span><span>runner ' + esc(c.runner || '—') + '</span>';
    if (!FINISHED[c.state]) {
      return h.head('TT-323 · Campaign', c.ref, 'Still ' + esc(c.state) + ': ' + c.evaluations + ' of ' + c.budget + ' evaluations so far.', meta, h.btn('Watch it live', { href: '/campaigns/' + c.ref + '/live' }));
    }
    if (c.state !== 'done') {
      return h.head('TT-323 · Campaign', c.ref, 'This campaign ' + esc(c.state) + '.', meta, h.btn('Plan another', { href: '/campaigns/new' })) +
        panel('What happened', '<pre class="code">' + esc(c.error || 'no reason was recorded') + '</pre>');
    }
    var res = c.result, modes = c.modes;
    var rate = c.method === 'random' ? (function () { var w = wilson(res.failures, res.evaluations); return res.failures + ' of ' + res.evaluations + ' uniform samples violated a rule: a 95% Wilson interval of ' + (100 * w[0]).toFixed(1) + '–' + (100 * w[1]).toFixed(1) + '%, over the declared box only.'; })()
      : (100 * res.failures / res.evaluations).toFixed(1) + '% of directed evaluations violated a rule. That describes the search, not the robot: the search goes looking for failures. Only a uniform campaign supports a rate.';
    var modeRows = modes.map(function (m) {
      return { href: '#/campaigns/' + c.ref + '/modes/' + m.ordinal, cells: ['<a href="#/campaigns/' + c.ref + '/modes/' + m.ordinal + '">' + esc(m.label) + '</a>', m.required.length + (m.required.length > 1 ? ' axes' : ' axis'),
        m.required.map(function (a) { return '<span class="m">' + esc(a) + ' ' + esc(fmtVal(a, m.minimal[a])) + '</span>'; }).join('<br>'), (+m.first_t).toFixed(2) + ' s', String(m.count), m.replay ? '3D' : 'trace'] };
    });
    var pts = (c._evs || []).map(function (e) { return point(c.spec, e); });
    var env = res.environment;
    return h.head('TT-323 · Campaign result', c.ref, esc(c.robot) + ' and ' + esc(c.policy) + ', searched over ' + Object.keys(c.spec.axes).length + ' axes for ' + c.budget + ' evaluations' + (c.duration_s ? ' in ' + c.duration_s + ' s' : '') + '.', meta,
      h.btn('Run it again', { act: 'rerun', line: true }) + h.btn('Plan another', { href: '/campaigns/new' })) +
      (modes.length ? '<div class="banner banner--inv" style="margin-bottom:18px"><span class="banner__sw" aria-hidden="true"></span><div class="banner__body"><p class="banner__t">' + modes.length + ' failure mode' + (modes.length > 1 ? 's' : '') + ' found</p>' +
        '<p class="banner__d">Smallest: ' + modes[0].required.map(function (a) { return esc(a) + ' ' + esc(fmtVal(a, modes[0].minimal[a])); }).join(' with ') + ', breaching at ' + (+modes[0].first_t).toFixed(2) + ' s. Found in simulation, MuJoCo ' + esc(env.mujoco) + '; nothing here was run on hardware.</p></div></div>'
        : '<div class="banner" style="margin-bottom:18px"><div class="banner__body"><p class="banner__t">No violations found</p><p class="banner__d">That bounds nothing: this budget, in this space, did not find one.</p></div></div>') +
      (modes.length ? '<div class="grid">' + panel('Failure modes · the ' + res.reduced + ' most severe of ' + res.failures + ' violations, reduced and grouped', h.table(['failure mode', 'needs', 'minimal case', { t: 'first breach', m: 1, r: 1 }, { t: 'count', m: 1, r: 1 }, 'replay'], modeRows), { flush: true,
        foot: 'Each minimal case is locally minimal: no single axis can be relaxed further within its tolerance. It is not proven globally smallest.' }) + '</div>' : '') +
      '<div class="grid grid--2" style="margin-top:18px">' + panel('Where the evaluations landed', scatterFor(c.spec, pts) + '<p class="note-line">' + rate + '</p>') +
      panel('Coverage', F.coverage(res.coverage.per_axis) + '<p class="note-line">' + res.coverage.cells_visited + ' of ' + res.coverage.cells_total + ' cells visited (' + (100 * res.coverage.fraction_visited).toFixed(2) + '%) at ' + res.coverage.bins_per_axis + ' bins per axis. Coverage says where the search looked.</p>') + '</div>' +
      '<div class="grid grid--2" style="margin-top:18px">' + panel('Environment', h.kv([['harness', 'faultline ' + esc(res.harness)], ['mujoco', esc(env.mujoco)], ['numpy', esc(env.numpy)], ['python', esc(env.python)], ['platform', esc(env.platform)],
        ['robot', '<span class="hash">' + esc(res.robot.sha256) + '</span>'], ['policy', '<span class="hash">' + esc(res.policy.id) + '</span>'], ['config', '<span class="hash">' + esc(res.base_config_sha256) + '</span>']])) +
      panel('The spec', h.code(esc(yaml(c.spec).replace(/^\n/, ''))) + '<p class="note-line">Saved as <code>spec.yaml</code>, <code>teeter campaign run spec.yaml</code> runs it again: the same seeds and environment give the same samples.</p>') + '</div>';
  }, function (c) {
    var b = $('[data-act="rerun"]');
    if (b) b.addEventListener('click', function () {
      post('/campaigns', { spec: c.spec }).then(function (n) { h.toast(n.ref + ' queued: the same spec, so it should find the same'); h.go('/campaigns/' + n.ref + '/live'); }).catch(function (e) { h.toast(e.message); });
    });
  });

  /* failure mode */
  S.mode = screen('the failure mode', function (p) {
    return get('/campaigns/' + p.id).then(function (c) {
      var m = (c.modes || [])[+p.m];
      if (!m) throw new Error(c.ref + ' has no mode ' + (+p.m + 1));
      var art = m.replay ? call('GET', '/campaigns/' + c.ref + '/artifacts/' + m.replay, undefined, true).then(function (r) { return r.json(); })
        : call('GET', '/campaigns/' + c.ref + '/artifacts/' + m.trace, undefined, true).then(function (r) { return r.text(); });
      return art.then(function (a) { return { c: c, m: m, replay: m.replay ? a : null, trace: m.replay ? null : a }; });
    });
  }, function (d, p) {
    var c = d.c, m = d.m, spec = c.spec, i = +p.m;
    var gone = Object.keys(spec.axes).filter(function (a) { return m.required.indexOf(a) < 0; });
    var rule = spec.predicates.filter(function (q) { return q.name === m.predicate; })[0];
    var tilt = spec.predicates.filter(function (q) { return q.signal === 'tilt_deg'; })[0];
    var traceHTML;
    if (d.replay) {
      traceHTML = F.trace({ hz: d.replay.hz, threshold: d.replay.threshold, nominal: d.replay.runs.nominal.tilt, minimal: d.replay.runs.minimal.tilt,
        minimalLabel: 'the minimal case', nominalLabel: 'unperturbed', label: 'Recorded tilt of the minimal case against the same robot unperturbed.' });
    } else {
      var rows = d.trace.trim().split('\n').slice(1).map(function (l) { return l.split(',').map(Number); });
      traceHTML = tilt ? F.trace({ hz: spec.control_hz, threshold: tilt.threshold, minimal: rows.map(function (r) { return r[1]; }), label: 'Recorded tilt of the minimal case.' })
        : '<p class="note-line">The rule watches ' + esc(rule.signal) + '; the trace is in the CSV.</p>';
    }
    var push = +(+m.minimal.push_impulse_ns).toFixed(4);     // as the minimal-case panel shows it
    return h.head('TT-324 · Failure mode', esc(m.label), 'Mode ' + (i + 1) + ' of ' + c.modes.length + ' in ' + c.ref + ': ' + m.count + ' of the ' + c.result.reduced + ' reduced failures fell here.',
      '<span><a href="#/campaigns/' + c.ref + '">' + c.ref + '</a></span><span>found in simulation</span>',
      (i > 0 ? h.btn('← Mode ' + i, { href: '/campaigns/' + c.ref + '/modes/' + (i - 1), line: true }) : '') + (i < c.modes.length - 1 ? h.btn('Mode ' + (i + 2) + ' →', { href: '/campaigns/' + c.ref + '/modes/' + (i + 1), line: true }) : '')) +
      '<div class="grid grid--12">' + panel('Minimal case', h.kv(m.required.map(function (a) { return [esc(a), '<span class="m">' + esc(fmtVal(a, m.minimal[a])) + '</span> · tolerance ' + (A.AX[a] ? A.AX[a].tolerance : '?')]; })
        .concat([['rule fired', '<span class="m">' + (+m.first_t).toFixed(2) + ' s</span> · <code>' + esc(rule.signal) + ' ' + esc(rule.op) + ' ' + rule.threshold + '</code>'], ['reduction', m.evaluations + ' evaluations'], ['locally minimal', m.locally_minimal ? 'yes' : 'no: the reduction budget ran out']])) +
        (gone.length ? '<p class="note-line"><b>Relaxed to nominal, and the failure remained:</b> ' + gone.map(function (a) { return '<code>' + esc(a) + '</code>'; }).join(', ') + '. These axes are not needed for this failure.</p>' : '') +
        '<p class="note-line">Locally minimal: no single axis can be relaxed further within its tolerance. Requested values are applied on the ' + spec.control_hz + ' Hz control grid, so what the robot received is quantised.</p>') +
      (d.replay ? panel('Replay', F.stage({ push: push, mujoco: c.result.environment.mujoco, threshold: d.replay.threshold, tag: c.ref + ' · mode ' + (i + 1) }), { flush: true, foot: 'Recorded by ' + esc(c.runner) + ' through the same simulation loop that produced the result. The body drawn around the recorded poses is a design, not the collision geometry. Drag to orbit.' })
        : panel('Replay', '<div class="wait" style="animation:none">No 3D replay for this robot.</div><p class="note-line">Replays are drawn for robots built like the stand-in quadruped. This mode\'s signals are in <code>' + esc(m.trace) + '</code>.</p>')) + '</div>' +
      '<div class="grid" style="margin-top:18px">' + panel('Recorded tilt', traceHTML) + '</div>' +
      '<div class="grid" style="margin-top:18px">' + panel('Re-run it yourself', h.code(h.sh(['teeter campaign run spec.yaml', '# spec.yaml: this campaign\'s spec, on its result page; the same seeds and environment give the same samples']))) + '</div>';
  }, function (d) {
    var stage = $('[data-replay]');
    if (!stage || !d.replay) return;
    var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches, stop = null;
    if (window.TeeterMachine && !reduced) {
      try { stop = window.TeeterMachine.mount(stage, d.replay, { offset: stage.clientWidth >= 640 ? [0.17, 0.02] : [0, 0] }); } catch (e) { stop = null; }
    }
    if (stop) A.cleanup.push(stop);
    else {
      var vw = stage.querySelector('.stage__view');
      if (vw) vw.insertAdjacentHTML('beforeend', '<p class="micro" style="position:absolute;left:44px;bottom:24px;z-index:2">3D replay needs WebGL and motion.</p>');
    }
  });

  /* runners */
  S.runners = screen('runners', function () { return Promise.all([get('/runners'), get('/campaigns?state=running&limit=50')]); }, function (d) {
    var busy = {};
    d[1].campaigns.forEach(function (c) { if (c.runner) busy[c.runner] = c.ref; });
    var rows = d[0].runners.map(function (r) {
      return { cells: ['<span class="ink">' + esc(r.name) + '</span>', h.verdict(!r.online ? 'offline' : busy[r.name] ? 'busy' : 'idle', !r.online ? 'Offline' : busy[r.name] ? 'Busy' : 'Idle'),
        '<span title="' + esc(r.host.platform || '') + '">' + esc(shortPlatform(r.host.platform) || r.host.hostname || '—') + '</span>', String(r.cores), esc(r.versions.harness || '?'), esc(r.versions.mujoco || '?'), esc(r.versions.python || '?'),
        busy[r.name] ? '<a href="#/campaigns/' + busy[r.name] + '/live">' + busy[r.name] + '</a>' : '—', r.robots.map(esc).join(', '), r.policies.map(esc).join(', '), ago(r.last_seen_at)] };
    });
    return h.head('TT-351 · Runners', 'Runners', 'Machines that run this workspace\'s campaigns. Each dials out to this server; nothing here can reach in, and each runs only the robots and policies its own config lists.', null, h.btn('Add a runner', { act: 'addrunner' })) +
      panel(count(rows.length, 'runner'), rows.length ? h.table(['runner', 'state', 'platform', { t: 'cores', r: 1, m: 1 }, { t: 'harness', m: 1 }, { t: 'mujoco', m: 1 }, { t: 'python', m: 1 }, 'job', 'robots', 'policies', 'seen'], rows, { stack: true })
        : '<p class="note-line" style="padding:14px">No runner has connected yet. Add one: it takes a token and two commands.</p>', { flush: true,
        foot: 'Results compare only across matching environments: a gate refuses two campaigns run on different MuJoCo builds.' });
  }, function () {
    $('[data-act="addrunner"]').addEventListener('click', function () {
      var m = modal('Add a runner', '<label class="f"><span class="f__l">Name it after the machine</span><input class="in" data-name value="lab-' + Math.random().toString(36).slice(2, 6) + '"></label>' +
        '<p class="note-line">This makes a runner token: it can claim this workspace\'s jobs and nothing else. It is shown once.</p><div class="acts"><button type="button" class="btn btn--sm" data-act="mint">Make the token</button><button type="button" class="btn btn--sm btn--line" data-act="close">Cancel</button></div><div data-out></div>');
      m.querySelector('[data-act="mint"]').addEventListener('click', function () {
        var name = m.querySelector('[data-name]').value.trim() || 'runner';
        post('/tokens', { name: name, kind: 'runner' }).then(function (t) {
          m.querySelector('[data-out]').innerHTML = '<p class="f__l" style="margin-top:12px">Token, shown once</p><pre class="code">' + esc(t.secret) + '</pre>' +
            '<p class="f__l">On the machine</p><pre class="code">' + esc(t.install.join('\n').replace('<machine name>', name)) + ' --config runner.yaml</pre>' +
            '<p class="f__l">runner.yaml: the only robots and policies it will run</p><pre class="code">robots:\n  quadruped: path/to/quadruped.xml\npolicies:\n  stand: stand\n  my-policy: onnx:/path/to/policy.onnx</pre>' +
            '<div class="acts"><button type="button" class="btn btn--sm btn--line" data-act="close">Done</button></div>';
          m.querySelector('[data-act="mint"]').disabled = true;
        }).catch(function (e) { m.querySelector('[data-out]').innerHTML = '<p class="note-line">' + esc(e.message) + '</p>'; });
      });
    });
  });

  /* programs */
  S.program = screen('the program', function (p) { return get('/programs/' + p.p); }, function (pr) {
    var base = pr.checkpoints.filter(function (c) { return c.baseline; })[0];
    var rows = pr.checkpoints.map(function (ck) {
      var lc = ck.latest_campaign;
      return { cells: ['<span class="ink">' + esc(ck.label) + '</span>' + (ck.baseline ? ' <span class="src">baseline</span>' : ''), '<code>' + esc(ck.policy) + '</code>', esc(ck.note || ''),
        lc ? ref(lc) + ' ' + stateChip(lc.state) : '—', lc && lc.modes_found != null ? String(lc.modes_found) : '—',
        ck.baseline ? '<button type="button" class="btn btn--sm btn--line" data-act="run:' + esc(ck.label) + '" title="Run the standard spec with ' + esc(ck.label) + '">Run</button>'
          : '<button type="button" class="btn btn--sm btn--line" data-act="gate:' + esc(ck.label) + '" title="Gate ' + esc(ck.label) + ' against ' + esc(base ? base.label : 'the baseline') + '" aria-label="Gate ' + esc(ck.label) + ' against ' + esc(base ? base.label : 'the baseline') + '">Gate</button>'] };
    });
    return h.head('TT-311 · Program', esc(pr.name), 'Every checkpoint runs the same experiment: this program\'s standard spec, with only the policy changed. Gating one compares it with the baseline\'s run of that experiment.',
      '<span>robot <b>' + esc(pr.standard_spec.robot) + '</b></span><span>' + Object.keys(pr.standard_spec.axes).length + ' axes · ' + methodName(pr.standard_spec.search.method) + ' · ' + pr.standard_spec.search.budget + ' evaluations</span>') +
      panel('Checkpoints', h.table(['checkpoint', 'policy', 'note', 'latest campaign', { t: 'modes', r: 1, m: 1 }, ''], rows, { stack: true }), { flush: true,
        foot: 'The demo checkpoints hold poses; they are not trained policies. CI calls the same thing: <code>teeter gate --program ' + esc(pr.slug) + ' --checkpoint &lt;label&gt;</code>, exit 1 when blocked.' }) +
      '<div class="grid" style="margin-top:18px">' + panel('Standard spec', h.code(esc(yaml(pr.standard_spec).replace(/^\n/, '')))) + '</div>';
  }, function (pr) {
    $$('[data-act^="gate:"]').forEach(function (b) {
      b.addEventListener('click', function () {
        b.disabled = true;
        post('/programs/' + pr.slug + '/gate', { checkpoint: b.getAttribute('data-act').slice(5) }).then(function (g) { h.go('/gates/' + g.ref); })
          .catch(function (e) { b.disabled = false; h.toast(e.message); });
      });
    });
    $$('[data-act^="run:"]').forEach(function (b) {
      b.addEventListener('click', function () {
        b.disabled = true;
        post('/programs/' + pr.slug + '/checkpoints/' + encodeURIComponent(b.getAttribute('data-act').slice(4)) + '/run')
          .then(function (c) { h.go('/campaigns/' + c.ref + '/live'); }).catch(function (e) { b.disabled = false; h.toast(e.message); });
      });
    });
  });
  S.checkpoints = S.program;

  /* gates */
  S.gates = screen('gates', function () { return get('/gates?limit=100'); }, function (d) {
    var rows = d.gates.map(function (g) {
      return { href: '#/gates/' + g.ref, cells: ['<a href="#/gates/' + g.ref + '">' + g.ref + '</a>', esc(progName(g.program, g.program_name)), esc(ckName(g.candidate)) + ' <span class="note-line">(' + g.candidate.ref + ')</span>', esc(ckName(g.baseline)) + ' <span class="note-line">(' + g.baseline.ref + ')</span>', stateChip(g.verdict || g.state), ago(g.created_at)] };
    });
    return h.head('TT-330 · Gates', 'Gates', 'Each compares a checkpoint\'s campaign with its baseline\'s, and only when both ran the same experiment.') +
      panel(count(rows.length, 'gate'), rows.length ? h.table(['gate', 'program', 'candidate', 'baseline', 'verdict', 'created'], rows, { stack: true }) : '<p class="note-line" style="padding:14px">No gates yet. Gate a checkpoint from its program\'s page.</p>', { flush: true });
  });
  var CHANGE = { widened: 'fail', 'new': 'fail', narrowed: 'passed', unchanged: 'none', not_found: 'refused' };
  var CHANGE_NOTE = { widened: 'fails under a smaller condition than the baseline', 'new': 'not found for the baseline', narrowed: 'needs a larger condition than the baseline',
    unchanged: 'the same minimal case, within tolerance', not_found: 'found for the baseline; not found this time, which is not evidence it is gone' };
  S.gate = screen('the gate', function (p) { return get('/gates/' + p.id); }, function (g) {
    var meta = '<span>' + esc(g.program ? progName(g.program, g.program_name) : 'no program') + '</span><span>candidate <a href="#/campaigns/' + g.candidate.ref + '">' + g.candidate.ref + '</a> · ' + esc(g.candidate.state) + '</span><span>baseline <a href="#/campaigns/' + g.baseline.ref + '">' + g.baseline.ref + '</a> · ' + esc(g.baseline.state) + '</span>';
    var title = esc(ckName(g.candidate)) + ' against ' + esc(ckName(g.baseline));
    if (g.state !== 'decided') {
      return h.head('TT-331 · Compare checkpoints', title, 'Waiting for both campaigns to finish. This page follows them.', meta) +
        '<div class="wait">' + esc(g.candidate.ref) + ' is ' + esc(g.candidate.state) + '; ' + esc(g.baseline.ref) + ' is ' + esc(g.baseline.state) + '.</div>';
    }
    var cmp = g.comparison;
    if (g.verdict === 'refused') {
      return h.head('TT-331 · Compare checkpoints', title, 'Not compared.', meta) +
        '<div class="banner"><div class="banner__body"><p class="banner__t">' + h.verdict('refused') + ' &nbsp;' + esc(cmp.reason) + '</p>' +
        '<p class="banner__d">A comparison across a changed experiment looks meaningful and is not, so the gate refuses it and names the field.</p></div></div>';
    }
    var rows = cmp.modes.map(function (m) {
      return { cells: ['<span class="v v--' + CHANGE[m.change] + '">' + m.change.replace('_', ' ') + '</span>', '<span class="ink">' + esc(m.label) + '</span>',
        m.baseline ? m.required.map(function (a) { return esc(a) + ' ' + esc(fmtVal(a, m.baseline[a])); }).join('<br>') : '—',
        m.candidate ? m.required.map(function (a) { return esc(a) + ' ' + esc(fmtVal(a, m.candidate[a])); }).join('<br>') : '—', CHANGE_NOTE[m.change]] };
    });
    var blocked = g.verdict === 'blocked', t = cmp.tally;
    return h.head('TT-331 · Compare checkpoints', title, 'Same robot, space, rules, search and seeds; only the policy differs, so the comparison stands.', meta) +
      '<div class="banner' + (blocked ? ' banner--inv' : '') + '" style="margin-bottom:18px">' + (blocked ? '<span class="banner__sw" aria-hidden="true"></span>' : '') + '<div class="banner__body"><p class="banner__t">' + (blocked ? 'Blocked' : 'Passed') + ' · ' + t['new'] + ' new, ' + t.widened + ' widened</p><p class="banner__d">' + esc(cmp.reason) + '. Found in simulation.</p></div></div>' +
      '<div class="stats" style="margin-bottom:18px">' + ['widened', 'new', 'unchanged', 'narrowed', 'not_found'].map(function (k) { return h.stat(k.replace('_', ' '), String(t[k] || 0), CHANGE_NOTE[k]); }).join('') + '</div>' +
      panel('Failure modes, baseline against candidate', rows.length ? h.table(['change', 'mode', 'baseline', 'candidate', 'what it means'], rows, { stack: true }) : '<p class="note-line" style="padding:14px">Neither campaign found a failure mode.</p>', { flush: true,
        foot: 'Minimal cases are compared axis by axis in distance from nominal, with each axis\'s reduction tolerance as the margin.' });
  }, function (g, p, my) {
    if (g.state !== 'decided') A.later(function () { if (A.seq() === my) A.render(); }, 2000);
  });

  /* settings: the audit log and members are built; the other tabs are the prototype's */
  var LIVE_TABS = { audit: 'the audit log', members: 'the members' };
  var protoSettings = S.settings;
  S.settings = function (p) { return LIVE_TABS[p.tab] ? loading(LIVE_TABS[p.tab]) : protoSettings(p); };
  S.settings.after = function (p) {
    if (!LIVE_TABS[p.tab]) { if (protoSettings.after) protoSettings.after(p); return; }
    var my = A.seq();
    if (p.tab === 'members') { members(my); return; }
    get('/audit?limit=200').then(function (d) {
      if (A.seq() !== my) return;
      A.view.innerHTML = h.head('TT-360 · Settings', 'Audit log', 'Every write in this workspace: who, what, when, from where.') +
        panel(d.events.length >= 200 ? 'The latest 200 events' : count(d.events.length, 'event'), h.table(['time · UTC', 'who', 'what', 'target', 'from'], d.events.map(function (e) { return { cells: ['<span class="m">' + esc(e.at.replace('T', ' ').replace('Z', '')) + '</span>', esc(e.actor), '<code>' + esc(e.action) + '</code>', esc(e.target), esc(e.ip || '—')] }; }), { stack: true }), { flush: true });
      A.refresh();
    }).catch(function (e) { if (A.seq() === my) A.view.innerHTML = failure(e); });
  };

  // who may sign in, and as what: owners and admins invite, change and remove
  var ROLES = ['owner', 'admin', 'engineer', 'viewer'];
  var ROLE_CAN = [['owner', 'everything, including making other owners'], ['admin', 'members, runners and tokens, and all an engineer can do'],
    ['engineer', 'plan and cancel campaigns, add checkpoints, gate them'], ['viewer', 'read everything in the workspace, change nothing']];
  function members(my) {
    var head = h.head('TT-361 · Settings', 'Members', 'Who may sign in to ' + esc(st.me.workspace.name) + ', and as what. Only an address invited here gets in.');
    get('/members').then(function (d) {
      if (A.seq() !== my) return;
      var me = st.me.user ? st.me.user.email : '', mine = st.me.role;
      function roleOptions(cur) {
        return ROLES.filter(function (r) { return r !== 'owner' || mine === 'owner'; })
          .map(function (r) { return '<option' + (r === cur ? ' selected' : '') + '>' + r + '</option>'; }).join('');
      }
      var rows = d.members.map(function (m) {
        var self = m.email === me, locked = self || (m.role === 'owner' && mine !== 'owner');
        return { cells: ['<span class="ink">' + esc(m.email) + '</span>' + (self ? ' <span class="note-line">(you)</span>' : ''), esc(m.name || '—'),
          locked ? esc(m.role) : '<select class="sel in--sm" style="min-width:120px" data-role="' + esc(m.email) + '" aria-label="Role of ' + esc(m.email) + '">' + roleOptions(m.role) + '</select>',
          m.signed_in_with_workos ? 'WorkOS' : 'a link or a token',
          locked ? '' : '<button type="button" class="btn btn--sm btn--line" data-remove="' + esc(m.email) + '">Remove</button>'] };
      });
      A.view.innerHTML = head +
        panel('Invite someone', '<form class="inv" data-invite><label class="f"><span class="f__l">Email</span><input class="in" type="email" required placeholder="name@company.com" autocomplete="off" data-inv-email></label>' +
          '<label class="f"><span class="f__l">Role</span><select class="sel" data-inv-role>' + roleOptions('engineer') + '</select></label><button class="btn btn--sm" type="submit">Invite</button></form>' +
          '<p class="note-line" data-inv-msg>' + (st.methods.workos ? 'They sign in through WorkOS with this address.' : 'Until WorkOS is configured on this server, its operator sends a one-time link: <code>teeter-api link --workspace ' + esc(st.me.workspace.slug) + ' --email &lt;address&gt;</code>.') + '</p>') +
        '<div class="grid" style="margin-top:18px">' + panel(count(d.members.length, 'member'), h.table(['email', 'name', 'role', 'signs in with', ''], rows, { stack: true }), { flush: true }) + '</div>' +
        '<div class="grid" style="margin-top:18px">' + panel('Roles', h.table(['role', 'can'], ROLE_CAN.map(function (r) { return { cells: ['<span class="ink">' + r[0] + '</span>', r[1]] }; })), { flush: true }) + '</div>';
      A.refresh();
      function again() { if (A.seq() === my) members(my); }
      $('[data-invite]').addEventListener('submit', function (e) {
        e.preventDefault();
        var email = $('[data-inv-email]').value.trim(), role = $('[data-inv-role]').value;
        post('/members', { email: email, role: role }).then(function (r) { h.toast(r.email + ' invited as ' + r.role); again(); })
          .catch(function (err) { $('[data-inv-msg]').textContent = err.message; });
      });
      $$('[data-role]').forEach(function (sel) {
        sel.addEventListener('change', function () {
          post('/members', { email: sel.getAttribute('data-role'), role: sel.value }).then(function (r) { h.toast(r.email + ' is now ' + r.role); again(); })
            .catch(function (err) { h.toast(err.message); again(); });
        });
      });
      $$('[data-remove]').forEach(function (b) {
        b.addEventListener('click', function () {
          b.disabled = true;
          call('DELETE', '/members/' + encodeURIComponent(b.getAttribute('data-remove'))).then(function (r) { h.toast(r.email + ' removed'); again(); })
            .catch(function (err) { b.disabled = false; h.toast(err.message); });
        });
      });
    }).catch(function (e) {
      if (A.seq() !== my) return;
      A.view.innerHTML = head + '<div class="banner"><div class="banner__body"><p class="banner__t">Owners and admins manage members</p><p class="banner__d">' + esc(e.message) + '. Ask one of them to invite people or change a role.</p></div></div>';
    });
  }

  /* ── the shell, live ───────────────────────────────────── */
  var LIVE = { login: 1, auth: 1, overview: 1, campaigns: 1, newCampaign: 1, live: 1, campaign: 1, mode: 1, runners: 1, program: 1, checkpoints: 1, gates: 1, gate: 1 };
  A.hooks.title = 'Teeter';
  A.hooks.decorate = function (m, html) {
    if (!m.name || LIVE[m.name] || (m.name === 'settings' && m.p.tab === 'audit')) return html;
    return '<p class="proto-note"><span class="src src--example">example</span><span>Designed, not built yet: this screen shows example data, not ' + (st.me ? '<b>' + esc(st.me.workspace.name) + '</b>' : 'your workspace') + '.</span></p>' + html;
  };
  function isAdmin() { return !!st.me && (st.me.role === 'owner' || st.me.role === 'admin'); }
  var TAB_NAMES = { audit: 'Audit log', members: 'Members', workspace: 'Workspace', sso: 'SSO', plan: 'Plan', data: 'Data handling' };
  A.hooks.nav = function (cur, m) {
    if (m && m.name === 'settings') cur = 'settings:' + (m.p.tab || 'workspace');
    if (m && m.name === 'newCampaign') cur = 'campaigns';
    function item(href, label, key) { return '<a href="#' + href + '"' + (cur === key ? ' class="is-here" aria-current="page"' : '') + '>' + label + '</a>'; }
    return item('/', 'Overview', 'overview') +
      '<p class="nav__grp">Programs</p>' + (st.programs.length ? st.programs.map(function (p) { return item('/programs/' + p.slug, esc(p.name), 'p:' + p.slug); }).join('') : '<p class="note-line" style="padding:0 8px">none yet</p>') +
      '<p class="nav__grp">Work</p>' + item('/campaigns', 'Campaigns', 'campaigns') + item('/gates', 'Gates', 'gates') +
      '<p class="nav__grp">Workspace</p>' + item('/runners', 'Runners', 'runners') + (isAdmin() ? item('/settings/members', 'Members', 'settings:members') : '') + (canWrite() ? item('/settings/audit', 'Audit log', 'settings:audit') : '') +
      '<p class="nav__grp">Designed, not built yet</p>' + item('/evidence', 'Evidence', 'evidence') + item('/library', 'Spaces and rules', 'library') + item('/integrations', 'Integrations', 'integrations') + item('/onboarding/1', 'First-day setup', 'onboarding');
  };
  A.hooks.crumbs = function (m) {
    if (m.name === 'settings') return '<a href="#/">' + (st.me ? esc(st.me.workspace.name) : 'Workspace') + '</a><i>/</i><b>' + (TAB_NAMES[m.p.tab] || 'Settings') + '</b>';
    var base = A.crumbs(m).replace('Example Robotics', st.me ? esc(st.me.workspace.name) : 'Workspace');
    if (m.name === 'program' || m.name === 'checkpoints') {
      var pr = st.programs.filter(function (x) { return x.slug === m.p.p; })[0];
      base = base.replace(/<a href="#\/programs\/[^"]*">[^<]*<\/a>/, '<a href="#/programs/' + esc(m.p.p) + '">' + esc(pr ? pr.name : m.p.p) + '</a>');
    }
    return base;
  };

  function signOut() { setToken(''); st.me = null; shell(); h.go('/login'); }
  function shell() {
    var me = st.me, banner = document.querySelector('.proto'), ro = !!me && !canWrite();
    // the strip stays only for a read-only visit, which must not be mistaken for a membership
    if (banner) {
      banner.hidden = !ro;
      if (ro) {
        banner.innerHTML = '<span class="proto__tag">Read-only</span><span class="proto__text">A visit to <b>' + esc(me.workspace.name) + '</b>: real campaigns from a real runner, on a stand-in quadruped whose checkpoints hold a pose rather than run a trained policy.</span>';
      }
    }
    document.documentElement.style.setProperty('--strip', ro ? '34px' : '0px');
    var ws = document.querySelector('.ws');
    if (ws && me) {
      ws.querySelector('.ws__mark').textContent = me.workspace.name.replace(/[^A-Za-z ]/g, '').split(' ').map(function (w) { return w.charAt(0); }).join('').slice(0, 2).toUpperCase() || 'TT';
      ws.querySelector('.ws__name').innerHTML = esc(me.workspace.name) + '<span class="ws__plan">' + esc(st.host) + '</span>';
      ws.setAttribute('data-go', '/');
    }
    var foot = document.getElementById('side-foot');
    if (foot) {
      var demo = !!me && /^tt_demo_/.test(me.token.prefix || '');
      var who = !me ? '' : demo ? 'Demo visitor' : me.user ? me.user.email : me.token.name;
      foot.innerHTML = me ? '<div class="me"><span class="me__av" aria-hidden="true">' + esc(who.charAt(0).toUpperCase() || '·') + '</span><span class="me__who"><span class="me__mail" title="' + esc(who) + '">' + esc(who) + '</span>' +
        '<span class="me__role">' + esc(ro ? 'read-only' : me.role || me.token.kind) + '</span></span><button class="me__out" type="button" data-signout-side>' + (ro ? 'Leave' : 'Sign out') + '</button></div>' : '';
      var out = foot.querySelector('[data-signout-side]');
      if (out) out.addEventListener('click', signOut);
    }
    document.body.classList.add('is-live');
    document.body.classList.toggle('is-readonly', !!me && !canWrite());
  }

  A.hooks.palette = function () {
    var out = [['Overview', '/'], ['Campaigns', '/campaigns'], ['Gates', '/gates'], ['Runners', '/runners']];
    if (canWrite()) out.splice(2, 0, ['New campaign', '/campaigns/new']);
    if (isAdmin()) out.push(['Members', '/settings/members']);
    if (canWrite()) out.push(['Audit log', '/settings/audit']);
    st.programs.forEach(function (p) { out.push(['Program · ' + p.name, '/programs/' + p.slug]); });
    st.recent.forEach(function (x) { out.push(x); });
    return out;
  };
  function recent() {
    Promise.all([get('/campaigns?limit=20'), get('/gates?limit=20')]).then(function (d) {
      st.recent = d[0].campaigns.map(function (c) { return [c.ref + ' · ' + c.robot + ' · ' + c.policy + ' · ' + c.state, '/campaigns/' + c.ref + (FINISHED[c.state] ? '' : '/live')]; })
        .concat(d[1].gates.map(function (g) { return [g.ref + ' · ' + ckName(g.candidate) + ' against ' + ckName(g.baseline) + ' · ' + (g.verdict || g.state), '/gates/' + g.ref]; }));
    }, function () { /* the palette keeps the screens */ });
  }
  document.querySelector('[data-palette="open"]').addEventListener('click', function () { if (st.me) recent(); });

  // render once: start the app if it has not started, otherwise draw again
  function show() { if (A.isStarted()) A.render(); else A.start(); }
  function boot() {
    if (!getToken()) {
      st.me = null; shell();
      if (!/^#\/(login|auth)/.test(location.hash)) history.replaceState(null, '', location.pathname + '#/login');
      show();
      return;
    }
    Promise.all([get('/me'), get('/programs')]).then(function (d) {
      st.me = d[0]; st.programs = d[1].programs;
      shell();
      recent();
      if (/^#\/(login|auth)/.test(location.hash)) history.replaceState(null, '', location.pathname + '#/');
      show();
    }).catch(function () { setToken(''); st.me = null; shell(); history.replaceState(null, '', location.pathname + '#/login'); show(); });
  }

  /* ── is a control plane serving this page? ─────────────── */
  var auth = /^#\/auth\/(tt_[A-Za-z0-9_\-]+)/.exec(location.hash);
  var ctl = 'AbortController' in window ? new AbortController() : null;
  var decided = false;
  function asPrototype() { if (!decided) { decided = true; prototype(); } }
  A.hold();                                       // this file decides: the prototype's own timer stands down
  if (/\/teeter\/app\//.test(location.pathname)) { asPrototype(); return; }   // the static site serves the prototype here
  var timer = setTimeout(function () { if (ctl) ctl.abort(); asPrototype(); }, 1500);
  fetch('/v1/health', { cache: 'no-store', signal: ctl ? ctl.signal : undefined })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) {
      clearTimeout(timer);
      if (decided) return;
      if (!j || j.service !== 'teeter-api') { asPrototype(); return; }
      decided = true;                             // a control plane answered: the app is live
      A.ROUTES.unshift(['/auth/:token', 'auth', { bare: 1, crumb: 'Signing in' }]);
      A.ROUTES.unshift(['/campaigns/new', 'newCampaign', { nav: 'campaigns-new', crumb: 'New campaign' }]);
      if (auth) { setToken(auth[1]); history.replaceState(null, '', location.pathname + '#/'); }
      // what the sign-in page should offer: links and tokens always; an
      // identity provider and a read-only demo when this server has them
      fetch('/v1/auth/methods', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; })
        .then(function (m) { if (m) st.methods = m; }, function () { /* keep the defaults */ })
        .then(boot);
    })
    .catch(function () { clearTimeout(timer); asPrototype(); });
}());
