/* Campaign builder.
 *
 * Everything here mirrors harness/faultline/config.py. The lists below are the
 * contract: SEVERITY_AXES from reduce.py, the signals Trajectory computes, and
 * the key sets config.py accepts. harness/tests/test_configure_page.py reads
 * this file and fails if any of them drift from the Python.
 *
 * No framework, no build step, no network. */

'use strict';

/* ── the contract ─────────────────────────────────────────────── */

// order and names match SEVERITY_AXES in harness/faultline/reduce.py
const AXES = [
  { name: 'push_impulse_ns',  unit: 'N·s', label: 'A shove to the torso',
    hint: 'Impulse delivered to the body mid-run.', min: 0, max: 16, step: 0.5, on: true },
  { name: 'slope_deg',        unit: 'deg', label: 'Ground incline',
    hint: 'How steep the floor is under the robot.', min: 0, max: 12, step: 0.5, on: true },
  { name: 'sensor_lag_ms',    unit: 'ms',  label: 'Sensor delay',
    hint: 'How late the policy sees the world.', min: 0, max: 50, step: 1, on: true },
  { name: 'torque_loss_pct',  unit: '%',   label: 'Actuator weakness',
    hint: 'Strength lost in the motors, 0–100.', min: 0, max: 40, step: 1, on: false },
  { name: 'payload_kg',       unit: 'kg',  label: 'Extra mass',
    hint: 'Additional load carried on the torso.', min: 0, max: 3, step: 0.1, on: false },
  { name: 'payload_offset_m', unit: 'm',   label: 'Load offset',
    hint: 'How far off centre that mass sits.', min: 0, max: 0.15, step: 0.01, on: false },
  { name: 'friction_mu',      unit: '–',   label: 'Floor friction',
    hint: 'Nominal comes from the model itself, not from zero.', min: 0.3, max: 1.0, step: 0.05, on: false },
];

// the only signals Trajectory.signal() resolves — harness/faultline/runner.py
const SIGNALS = ['tilt_deg', 'height_m', 'contact_force_n', 'joint_vel_rads'];

// METHODS in harness/faultline/search.py
const METHODS = ['random', 'cem'];

// key sets in harness/faultline/config.py
const TOP_LEVEL   = ['robot', 'policy', 'duration_s', 'control_hz', 'seeds',
                     'axes', 'predicates', 'search', 'reduce', 'report'];
const SEARCH_KEYS = ['method', 'budget', 'target'];
const REDUCE_KEYS = ['enabled', 'max', 'budget'];
const REPORT_KEYS = ['out', 'bins'];

const CAD_EXT = ['step', 'stp', 'iges', 'igs', 'sldprt', 'sldasm', 'f3d', 'ipt', 'catpart', 'x_t'];

/* ── state ────────────────────────────────────────────────────── */

const state = {
  robotPath: 'my_robot.urdf',
  model: null,              // parse result, or null
  policyMode: 'stand',
  policyRef: '',
  duration: 5,
  seedSampler: 41279,
  method: 'cem',
  budget: 150,
  axes: AXES.map(a => ({ name: a.name, on: a.on, min: a.min, max: a.max })),
  preds: [{ name: 'tilt_limit', signal: 'tilt_deg', op: '>', threshold: 35, grace_s: 0.3 }],
};

const $ = sel => document.querySelector(sel);

/* ── model parsing ────────────────────────────────────────────── */

/* MJCF puts template <joint> elements inside <default>. Counting those as real
 * joints would report 13 on a 12-joint robot, so every query skips defaults. */
function inDefault(el) {
  for (let p = el.parentElement; p; p = p.parentElement) {
    if (p.tagName === 'default') return true;
  }
  return false;
}

function real(nodes) {
  return Array.from(nodes).filter(n => !inDefault(n));
}

function parseModel(text, filename) {
  const doc = new DOMParser().parseFromString(text, 'application/xml');
  if (doc.querySelector('parsererror')) {
    throw new Error('This file is not valid XML. Check it opens in a text editor.');
  }
  const root = doc.documentElement;
  if (root.tagName === 'mujoco') return parseMjcf(doc, filename);
  if (root.tagName === 'robot')  return parseUrdf(doc, filename);
  throw new Error(
    `Root element is <${root.tagName}>. A MuJoCo model starts with <mujoco> and ` +
    `a URDF with <robot>.`
  );
}

function parseMjcf(doc, filename) {
  const joints = real(doc.querySelectorAll('joint'));
  const free = real(doc.querySelectorAll('freejoint'))
    .concat(joints.filter(j => j.getAttribute('type') === 'free'));
  const hinged = joints.filter(j => j.getAttribute('type') !== 'free');

  const actEl = doc.querySelector('actuator');
  const actuators = actEl ? Array.from(actEl.children).filter(c => c.nodeType === 1) : [];

  let friction = null;
  for (const g of real(doc.querySelectorAll('geom'))) {
    if (g.getAttribute('name') === 'floor' || g.getAttribute('type') === 'plane') {
      const f = g.getAttribute('friction');
      if (f) { friction = parseFloat(f.trim().split(/\s+/)[0]); break; }
    }
  }

  return {
    format: 'MJCF',
    filename,
    joints: hinged.length,
    jointNames: hinged.map(j => j.getAttribute('name')).filter(Boolean),
    free: free.length,
    actuators: actuators.length,
    friction,
    keyframe: !!doc.querySelector('keyframe key'),
    bodies: real(doc.querySelectorAll('body')).length,
  };
}

function parseUrdf(doc, filename) {
  const joints = Array.from(doc.querySelectorAll('joint'));
  const movable = joints.filter(j => (j.getAttribute('type') || '') !== 'fixed');
  return {
    format: 'URDF',
    filename,
    joints: movable.length,
    jointNames: movable.map(j => j.getAttribute('name')).filter(Boolean),
    fixed: joints.length - movable.length,
    free: 0,
    actuators: doc.querySelectorAll('transmission').length,
    friction: null,
    keyframe: false,
    bodies: doc.querySelectorAll('link').length,
  };
}

async function sha256(buffer) {
  if (!(window.crypto && crypto.subtle)) return null;   // needs a secure context
  try {
    const d = await crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(d)).map(b => b.toString(16).padStart(2, '0')).join('');
  } catch { return null; }
}

/* ── file intake ──────────────────────────────────────────────── */

async function takeFile(file) {
  const out = $('#robot-readout');
  const ext = (file.name.split('.').pop() || '').toLowerCase();

  if (CAD_EXT.includes(ext)) {
    state.model = null;
    out.innerHTML = card('warn', 'That is a CAD file, not a robot model.', `
      <p>CAD describes shape. A simulator needs what CAD leaves out — joint axes and
      limits, link masses, and inertia tensors — so <code>.${esc(ext)}</code> cannot be
      simulated directly.</p>
      <p>The usual route is to export URDF from the CAD tool itself: SolidWorks has
      <em>sw2urdf</em>, Onshape has <em>onshape-to-robot</em>, Fusion has
      <em>fusion2urdf</em>. Each writes the joints and inertias alongside the meshes.
      Bring the URDF back here.</p>`);
    render();
    return;
  }

  let text, buffer;
  try {
    buffer = await file.arrayBuffer();
    text = new TextDecoder().decode(buffer);
  } catch {
    out.innerHTML = card('err', 'Could not read that file.', '');
    render();
    return;
  }

  let m;
  try {
    m = parseModel(text, file.name);
  } catch (e) {
    state.model = null;
    out.innerHTML = card('err', 'Could not read that as a robot model.',
      `<p>${esc(e.message)}</p>`);
    render();
    return;
  }

  m.hash = await sha256(buffer);
  m.bytes = file.size;
  state.model = m;
  if (state.robotPath === 'my_robot.urdf' || !state.robotPath) {
    state.robotPath = file.name;
    $('#robot-path').value = file.name;
  }

  const rows = [
    ['format', m.format],
    ['moving joints', String(m.joints)],
    ['actuators', m.format === 'URDF' ? `${m.actuators} transmissions` : String(m.actuators)],
    [m.format === 'URDF' ? 'links' : 'bodies', String(m.bodies)],
  ];
  if (m.free) rows.push(['free joint', `${m.free} (floating base)`]);
  if (m.fixed) rows.push(['fixed joints', String(m.fixed)]);
  if (m.friction !== null) rows.push(['floor friction', String(m.friction)]);
  if (m.hash) rows.push(['sha-256', m.hash.slice(0, 16) + '…']);

  out.innerHTML = card('ok', `Read ${esc(m.filename)}.`,
    `<dl class="facts mono">${rows.map(([k, v]) =>
      `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>` + modelNotes(m));
  render();
}

function modelNotes(m) {
  const notes = [];
  if (m.joints === 0) {
    notes.push('No moving joints found. Either the file describes a fixed object, or the joints sit somewhere this parser did not look.');
  }
  if (m.format === 'MJCF' && m.actuators === 0) {
    notes.push('No actuators. A policy has nothing to drive without them.');
  }
  if (m.format === 'MJCF' && m.actuators && m.joints && m.actuators !== m.joints) {
    notes.push(`${m.actuators} actuators against ${m.joints} moving joints — fine if deliberate, worth checking if not.`);
  }
  if (m.format === 'URDF') {
    notes.push('A URDF carries no contact parameters and no actuator dynamics worth trusting. After conversion, check friction, joint damping and gear ratios before believing a result.');
  }
  return notes.length
    ? `<ul class="notes">${notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>` : '';
}

/* ── rendering the dynamic sections ───────────────────────────── */

function renderAxes() {
  $('#axes').innerHTML = AXES.map((a, i) => {
    const s = state.axes[i];
    return `
    <div class="axis${s.on ? ' is-on' : ''}">
      <label class="axis__head">
        <input type="checkbox" data-axis="${i}" ${s.on ? 'checked' : ''}>
        <span class="axis__name">${esc(a.label)}</span>
        <code class="axis__key mono">${esc(a.name)}</code>
      </label>
      <p class="axis__hint">${esc(a.hint)}</p>
      <div class="axis__range">
        <label class="mini"><span>from</span>
          <input type="number" class="input input--sm mono" data-min="${i}"
                 value="${s.min}" step="${a.step}" ${s.on ? '' : 'disabled'}></label>
        <label class="mini"><span>to</span>
          <input type="number" class="input input--sm mono" data-max="${i}"
                 value="${s.max}" step="${a.step}" ${s.on ? '' : 'disabled'}></label>
        <span class="axis__unit mono">${esc(a.unit)}</span>
      </div>
    </div>`;
  }).join('');
}

function renderPreds() {
  $('#preds').innerHTML = state.preds.map((p, i) => `
    <div class="pred">
      <div class="pred__grid">
        <label class="mini mini--grow"><span>name</span>
          <input type="text" class="input input--sm mono" data-pname="${i}"
                 value="${esc(p.name)}" spellcheck="false"></label>
        <label class="mini mini--grow"><span>signal</span>
          <select class="input input--sm mono" data-psignal="${i}">
            ${SIGNALS.map(s => `<option value="${s}"${s === p.signal ? ' selected' : ''}>${s}</option>`).join('')}
          </select></label>
        <label class="mini"><span>when</span>
          <select class="input input--sm mono" data-pop="${i}">
            <option value=">"${p.op === '>' ? ' selected' : ''}>&gt;</option>
            <option value="<"${p.op === '<' ? ' selected' : ''}>&lt;</option>
          </select></label>
        <label class="mini"><span>threshold</span>
          <input type="number" class="input input--sm mono" data-pthr="${i}"
                 value="${p.threshold}" step="any"></label>
        <label class="mini"><span>grace (s)</span>
          <input type="number" class="input input--sm mono" data-pgrace="${i}"
                 value="${p.grace_s}" step="0.1" min="0"></label>
        <button type="button" class="x" data-pdel="${i}"
                aria-label="Remove rule ${esc(p.name)}"${state.preds.length < 2 ? ' disabled' : ''}>Remove</button>
      </div>
      <p class="pred__read">${predSentence(p)}</p>
    </div>`).join('');
}

function predSentence(p) {
  const words = {
    tilt_deg: 'the body tilts', height_m: 'the body height is',
    contact_force_n: 'contact force is', joint_vel_rads: 'joint velocity is',
  };
  const unit = { tilt_deg: '°', height_m: ' m', contact_force_n: ' N', joint_vel_rads: ' rad/s' };
  const cmp = p.op === '>' ? 'more than' : 'less than';
  const grace = p.grace_s > 0 ? `, ignoring the first ${p.grace_s} s` : '';
  return `Fails when ${words[p.signal] || p.signal} ${cmp} ${p.threshold}${unit[p.signal] || ''}${grace}.`;
}

/* ── validation — mirrors ConfigError in config.py ────────────── */

function validate() {
  const problems = [];

  if (!state.robotPath.trim()) problems.push(['robot', 'Needs a path to the model file.']);
  if (state.policyMode === 'module') {
    const ref = state.policyRef.trim();
    if (!ref) problems.push(['policy', 'Needs an import path, or use the baseline.']);
    else if (!ref.includes(':')) problems.push(['policy', `"${ref}" must be module:Attr — the module, a colon, then the object.`]);
  }

  const on = state.axes.filter(a => a.on);
  if (!on.length) problems.push(['axes', 'Turn on at least one thing to vary, or there is nothing to search.']);
  on.forEach(a => {
    if (!Number.isFinite(a.min) || !Number.isFinite(a.max)) problems.push([a.name, 'Both ends of the range need a number.']);
    else if (a.min >= a.max) problems.push([a.name, `Range is empty: from ${a.min} to ${a.max}.`]);
  });

  if (!state.preds.length) problems.push(['predicates', 'Needs at least one rule, or nothing can fail.']);
  const seen = new Set();
  state.preds.forEach(p => {
    if (!p.name.trim()) problems.push(['predicates', 'Every rule needs a name.']);
    else if (seen.has(p.name)) problems.push([p.name, 'Two rules share this name.']);
    seen.add(p.name);
    if (!SIGNALS.includes(p.signal)) problems.push([p.name, `Unknown signal ${p.signal}.`]);
    if (!['>', '<'].includes(p.op)) problems.push([p.name, 'Comparison must be > or <.']);
    if (!Number.isFinite(p.threshold)) problems.push([p.name, 'Threshold needs a number.']);
    if (!(p.grace_s >= 0)) problems.push([p.name, 'Grace period cannot be negative.']);
  });

  if (!METHODS.includes(state.method)) problems.push(['search', `Unknown method ${state.method}.`]);
  if (!Number.isFinite(state.budget) || state.budget < 1) problems.push(['budget', 'Budget must be at least 1.']);
  if (!Number.isFinite(state.duration) || state.duration <= 0) problems.push(['duration_s', 'Run length must be above zero.']);

  return problems;
}

/* Warnings are not errors — the config is valid, the run may still surprise. */
function warnings() {
  const w = [];
  const m = state.model;
  if (state.policyMode === 'stand' && m && !m.keyframe) {
    w.push('The baseline controller holds the model\'s own nominal stance, which it reads from a <keyframe>. This model has none, so the baseline will fail to start — add a keyframe, or point at your own policy.');
  }
  if (state.policyMode === 'stand' && m && m.format === 'URDF') {
    w.push('URDF carries no keyframe, so the built-in baseline has no stance to hold. Convert to MJCF and add one, or supply your own policy.');
  }
  const on = state.axes.filter(a => a.on).length;
  if (on >= 5 && state.budget < 400) {
    w.push(`${on} axes with a budget of ${state.budget} samples the volume thinly. Coverage will be honest about that, but expect to miss things.`);
  }
  return w;
}

/* ── YAML ─────────────────────────────────────────────────────── */

function num(n) {
  return Number.isInteger(n) ? String(n) : String(parseFloat(n.toFixed(6)));
}

function buildYaml() {
  const L = [];
  L.push('# built at faultline/configure');
  L.push('# every key is read by faultline/config.py');
  L.push('');
  L.push(`robot: ${state.robotPath.trim()}`);
  L.push(`policy: ${state.policyMode === 'stand' ? 'stand' : state.policyRef.trim()}`);
  L.push(`duration_s: ${num(state.duration)}`);
  L.push('');
  // comments sit on their own lines: trailing ones run past the preview pane
  L.push('# three seeds, not one — a single seed');
  L.push('# would hide which component diverged');
  L.push('seeds:');
  L.push(`  sampler: ${state.seedSampler}`);
  L.push('  sim: 0');
  L.push('  policy: 0');
  L.push('');
  L.push('# the volume to search, in physical units');
  L.push('axes:');
  const on = state.axes.filter(a => a.on);
  const pad = Math.max(...on.map(a => a.name.length), 1);
  on.forEach(a => {
    const unit = AXES.find(x => x.name === a.name).unit;
    const range = `[${num(a.min)}, ${num(a.max)}]`;
    L.push(`  ${(a.name + ':').padEnd(pad + 2)}${range.padEnd(12)}# ${unit}`);
  });
  L.push('');
  L.push('# what counts as a failure');
  L.push('# your rules, never a learned classifier');
  L.push('predicates:');
  state.preds.forEach(p => {
    L.push(`  - name: ${p.name}`);
    L.push(`    signal: ${p.signal}`);
    L.push(`    op: "${p.op}"`);          // quoted: bare > is a YAML block scalar
    L.push(`    threshold: ${num(p.threshold)}`);
    if (p.grace_s > 0) L.push(`    grace_s: ${num(p.grace_s)}`);
  });
  L.push('');
  L.push(`search: {method: ${state.method}, budget: ${state.budget}}`);
  L.push('reduce: {enabled: true, max: 10}');
  L.push('report: {out: deliverables/}');
  return L.join('\n') + '\n';
}

/* ── render ───────────────────────────────────────────────────── */

function render() {
  const problems = validate();
  const warns = warnings();
  const ok = problems.length === 0;

  $('#yaml').textContent = ok ? buildYaml() : '';
  $('#yaml').hidden = !ok;

  const badge = $('#status');
  badge.textContent = ok ? 'ready' : `${problems.length} to fix`;
  badge.className = 'badge ' + (ok ? 'badge--ok' : 'badge--err');

  const box = $('#problems');
  let html = '';
  if (problems.length) {
    html += `<ul class="problems__list">${problems.map(([f, m]) =>
      `<li><code class="mono">${esc(f)}</code> ${esc(m)}</li>`).join('')}</ul>`;
  }
  if (warns.length) {
    html += `<ul class="problems__list problems__list--warn">${warns.map(w =>
      `<li>${esc(w)}</li>`).join('')}</ul>`;
  }
  box.innerHTML = html;

  $('#download').disabled = !ok;
  $('#copy').disabled = !ok;

  const secs = (state.budget * state.duration / 12).toFixed(0);
  $('#budget-hint').textContent =
    `simulations · roughly ${secs < 60 ? secs + ' s' : (secs / 60).toFixed(0) + ' min'} on one core`;

  document.querySelectorAll('.axis').forEach((el, i) => {
    el.classList.toggle('is-on', state.axes[i].on);
  });
}

/* ── events ───────────────────────────────────────────────────── */

function esc(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function card(kind, title, body) {
  return `<div class="card card--${kind}"><p class="card__title">${title}</p>${body}</div>`;
}

function wire() {
  renderAxes();
  renderPreds();

  const drop = $('#drop');
  const input = $('#robot-file');
  input.addEventListener('change', e => { if (e.target.files[0]) takeFile(e.target.files[0]); });
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); drop.classList.add('is-over');
  }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); drop.classList.remove('is-over');
  }));
  drop.addEventListener('drop', e => {
    const f = e.dataTransfer.files[0];
    if (f) takeFile(f);
  });

  $('#robot-path').addEventListener('input', e => { state.robotPath = e.target.value; render(); });

  document.querySelectorAll('input[name="policy-mode"]').forEach(r => {
    r.addEventListener('change', e => {
      state.policyMode = e.target.value;
      $('#policy-ref-field').hidden = state.policyMode !== 'module';
      render();
    });
  });
  $('#policy-ref').addEventListener('input', e => { state.policyRef = e.target.value; render(); });

  $('#axes').addEventListener('input', e => {
    const t = e.target;
    if (t.dataset.axis !== undefined) {
      const i = +t.dataset.axis;
      state.axes[i].on = t.checked;
      document.querySelectorAll(`[data-min="${i}"],[data-max="${i}"]`).forEach(el => el.disabled = !t.checked);
    } else if (t.dataset.min !== undefined) state.axes[+t.dataset.min].min = parseFloat(t.value);
    else if (t.dataset.max !== undefined) state.axes[+t.dataset.max].max = parseFloat(t.value);
    render();
  });

  $('#preds').addEventListener('input', e => {
    const t = e.target, d = t.dataset;
    if (d.pname !== undefined) state.preds[+d.pname].name = t.value;
    else if (d.psignal !== undefined) state.preds[+d.psignal].signal = t.value;
    else if (d.pop !== undefined) state.preds[+d.pop].op = t.value;
    else if (d.pthr !== undefined) state.preds[+d.pthr].threshold = parseFloat(t.value);
    else if (d.pgrace !== undefined) state.preds[+d.pgrace].grace_s = parseFloat(t.value);
    else return;
    const row = t.closest('.pred');
    if (row) row.querySelector('.pred__read').textContent = predSentence(state.preds[+(d.pname ?? d.psignal ?? d.pop ?? d.pthr ?? d.pgrace)]);
    render();
  });

  $('#preds').addEventListener('click', e => {
    const i = e.target.dataset.pdel;
    if (i === undefined) return;
    state.preds.splice(+i, 1);
    renderPreds(); render();
  });

  $('#add-pred').addEventListener('click', () => {
    state.preds.push({ name: `rule_${state.preds.length + 1}`, signal: 'height_m', op: '<', threshold: 0.15, grace_s: 0 });
    renderPreds(); render();
  });

  $('#method').addEventListener('change', e => { state.method = e.target.value; render(); });
  $('#budget').addEventListener('input', e => { state.budget = parseInt(e.target.value, 10); render(); });
  $('#duration').addEventListener('input', e => { state.duration = parseFloat(e.target.value); render(); });
  $('#seed-sampler').addEventListener('input', e => { state.seedSampler = parseInt(e.target.value, 10) || 0; render(); });

  $('#download').addEventListener('click', () => {
    const blob = new Blob([buildYaml()], { type: 'application/x-yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'campaign.yaml';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  $('#copy').addEventListener('click', async e => {
    try {
      await navigator.clipboard.writeText(buildYaml());
      const b = e.target; const was = b.textContent;
      b.textContent = 'Copied'; setTimeout(() => { b.textContent = was; }, 1400);
    } catch { /* clipboard blocked; the text is selectable in the pane */ }
  });

  render();
}

document.addEventListener('DOMContentLoaded', wire);
