/* Faultline workspace — a local prototype.
 *
 * There is no server. Everything here lives in this browser's localStorage,
 * which is why there is no password: there is nothing to authenticate against
 * and storing one would teach a bad habit for no benefit. When a backend
 * exists, this file is the front end that talks to it.
 *
 * The answers are not decoration. Each one changes what the dashboard builds:
 * which axes to search, which rules to check, which policy loader applies,
 * and whether the regulation panel is relevant at all. */

'use strict';

const KEY = 'faultline.workspace.v1';

/* ── what each answer changes ─────────────────────────────────── */

const ROBOTS = {
  quadruped: {
    label: 'Legged — quadruped',
    axes: [['push_impulse_ns', 0, 16], ['slope_deg', 0, 14], ['friction_mu', 0.3, 1.0]],
    preds: [['tilt_limit', 'tilt_deg', '>', 35], ['height_floor', 'height_m', '<', 0.12]],
    why: 'Toppling is the dominant failure, so the rules watch body tilt and height.',
  },
  humanoid: {
    label: 'Legged — humanoid',
    axes: [['push_impulse_ns', 0, 22], ['slope_deg', 0, 10], ['sensor_lag_ms', 0, 60]],
    preds: [['tilt_limit', 'tilt_deg', '>', 25], ['height_floor', 'height_m', '<', 0.55]],
    why: 'A higher centre of mass topples sooner, so the tilt threshold is tighter than a quadruped’s.',
  },
  arm: {
    label: 'Fixed arm or manipulator',
    axes: [['payload_kg', 0, 5], ['payload_offset_m', 0, 0.2], ['torque_loss_pct', 0, 40]],
    preds: [['contact_limit', 'contact_force_n', '>', 150], ['joint_speed', 'joint_vel_rads', '>', 8]],
    why: 'A fixed base cannot fall, so the rules watch contact force and joint speed instead.',
  },
  mobile: {
    label: 'Mobile base / AMR',
    axes: [['friction_mu', 0.25, 1.0], ['slope_deg', 0, 8], ['sensor_lag_ms', 0, 80]],
    preds: [['tilt_limit', 'tilt_deg', '>', 20], ['contact_limit', 'contact_force_n', '>', 120]],
    why: 'Slip and late perception dominate, so friction and sensor delay lead the search.',
  },
};

const SYMPTOMS = {
  falls:    { label: 'It falls over',            emphasis: 'tilt_limit' },
  drops:    { label: 'It drops or crushes things', emphasis: 'contact_limit' },
  collides: { label: 'It hits things',           emphasis: 'contact_limit' },
  unknown:  { label: 'We don’t know yet',   emphasis: null },
};

const FORMATS = {
  pytorch: { label: 'PyTorch', policy: 'mypkg.policies:WalkPolicy', ready: true,
    note: 'Wrap your checkpoint in a class with <code>reset(seed)</code> and <code>act(obs, t)</code>.' },
  onnx:    { label: 'ONNX', policy: 'mypkg.policies:OnnxPolicy', ready: false,
    note: 'Loading <code>.onnx</code> directly is on the roadmap, not built. For now wrap your session in a class with <code>reset(seed)</code> and <code>act(obs, t)</code>.' },
  jax:     { label: 'JAX / Flax', policy: 'mypkg.policies:JaxPolicy', ready: false,
    note: 'No direct loader yet. Wrap your apply function in a class with <code>reset(seed)</code> and <code>act(obs, t)</code>.' },
  other:   { label: 'Something else', policy: 'mypkg.policies:MyPolicy', ready: true,
    note: 'Anything callable works, so long as it exposes <code>reset(seed)</code> and <code>act(obs, t)</code>.' },
};

const STAGES = {
  sim:      { label: 'Still in simulation', urgency: 'Now is the cheapest time to find these. Nothing has been built around the policy yet.' },
  lab:      { label: 'On lab hardware',     urgency: 'Every failure you find in simulation is one you do not have to find with the real robot.' },
  pilot:    { label: 'In a pilot',          urgency: 'A pilot means someone else is now standing near it. Failure modes are worth knowing before they scale.' },
  shipping: { label: 'Shipping to customers', urgency: 'Shipping into the EU brings 20 January 2027 into scope for you directly.' },
};

const QUESTIONS = [
  { id: 'robot', q: 'What are you testing?',
    help: 'This sets which conditions are worth searching and what counts as a failure.',
    opts: Object.entries(ROBOTS).map(([v, o]) => [v, o.label]) },
  { id: 'stage', q: 'Where is it today?',
    help: 'Changes what to do first, not what the harness does.',
    opts: Object.entries(STAGES).map(([v, o]) => [v, o.label]) },
  { id: 'symptom', q: 'When it goes wrong, what happens?',
    help: 'We lead the search with the rule that matches. "Don’t know" is a normal answer.',
    opts: Object.entries(SYMPTOMS).map(([v, o]) => [v, o.label]) },
  { id: 'format', q: 'What is the policy written with?',
    help: 'Decides how it gets loaded.',
    opts: Object.entries(FORMATS).map(([v, o]) => [v, o.label]) },
  { id: 'eu', q: 'Do you ship, or plan to ship, into the EU?',
    help: 'Machinery Regulation 2023/1230 applies from 20 January 2027. If it does not apply to you we leave it out.',
    opts: [['yes', 'Yes'], ['no', 'No'], ['unsure', 'Not sure yet']] },
];

/* ── state ────────────────────────────────────────────────────── */

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch { return null; }
}
function save(w) {
  try { localStorage.setItem(KEY, JSON.stringify(w)); } catch { /* private mode */ }
}
function clear() {
  try { localStorage.removeItem(KEY); } catch {}
}

let ws = load();
let step = 0;

const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ── views ────────────────────────────────────────────────────── */

function show(view) {
  ['auth', 'quiz', 'dash'].forEach(v => { $('#view-' + v).hidden = v !== view; });
  window.scrollTo(0, 0);
}

function renderAuth() {
  const existing = load();
  $('#returning').hidden = !existing;
  if (existing) $('#returning-name').textContent = existing.name || existing.email;
  show('auth');
}

function renderQuiz() {
  const q = QUESTIONS[step];
  const chosen = ws.answers[q.id];
  $('#quiz-progress').textContent = `${step + 1} of ${QUESTIONS.length}`;
  $('#quiz-bar').style.setProperty('--pct', ((step) / QUESTIONS.length * 100) + '%');
  $('#quiz-q').textContent = q.q;
  $('#quiz-help').textContent = q.help;
  $('#quiz-opts').innerHTML = q.opts.map(([v, label]) => `
    <button type="button" class="opt${chosen === v ? ' is-on' : ''}" data-v="${v}">
      <span class="opt__label">${esc(label)}</span>
      <span class="opt__tick" aria-hidden="true"></span>
    </button>`).join('');
  $('#quiz-back').hidden = step === 0;
  show('quiz');
}

function yaml(w) {
  const r = ROBOTS[w.answers.robot];
  const f = FORMATS[w.answers.format];
  const emph = SYMPTOMS[w.answers.symptom].emphasis;
  const preds = r.preds.slice().sort((a, b) => (b[0] === emph) - (a[0] === emph));
  const pad = Math.max(...r.axes.map(a => a[0].length));
  const L = [];
  L.push(`robot: ${w.answers.robot}.xml`);
  L.push(`policy: ${f.policy}`);
  L.push('duration_s: 5');
  L.push('');
  L.push('seeds:');
  L.push('  sampler: 41279');
  L.push('  sim: 0');
  L.push('  policy: 0');
  L.push('');
  L.push('axes:');
  r.axes.forEach(([n, lo, hi]) => L.push(`  ${(n + ':').padEnd(pad + 2)}[${lo}, ${hi}]`));
  L.push('');
  L.push('predicates:');
  preds.forEach(([n, sig, op, th]) => {
    L.push(`  - name: ${n}`);
    L.push(`    signal: ${sig}`);
    L.push(`    op: "${op}"`);
    L.push(`    threshold: ${th}`);
  });
  L.push('');
  L.push('search: {method: cem, budget: 150}');
  L.push('reduce: {enabled: true, max: 10}');
  return L.join('\n');
}

function renderDash() {
  const a = ws.answers;
  const r = ROBOTS[a.robot], f = FORMATS[a.format], st = STAGES[a.stage], sy = SYMPTOMS[a.symptom];

  $('#hello').textContent = ws.name ? ws.name.split(' ')[0] : 'there';
  $('#setup').innerHTML = `
    <dt>Robot</dt><dd>${esc(r.label)}</dd>
    <dt>Stage</dt><dd>${esc(st.label)}</dd>
    <dt>Symptom</dt><dd>${esc(sy.label)}</dd>
    <dt>Policy</dt><dd>${esc(f.label)}</dd>
    <dt>EU market</dt><dd>${a.eu === 'yes' ? 'Yes' : a.eu === 'no' ? 'No' : 'Undecided'}</dd>`;

  $('#why').textContent = r.why;
  $('#urgency').textContent = st.urgency;
  $('#yaml').textContent = yaml(ws);
  $('#fmt-note').innerHTML = f.note;
  $('#fmt-flag').hidden = f.ready;

  // the regulation panel only appears when it actually applies
  const euOn = a.eu === 'yes' || a.eu === 'unsure';
  $('#eu-panel').hidden = !euOn;
  if (euOn) {
    const days = Math.ceil((Date.UTC(2027, 0, 20) - Date.now()) / 86400000);
    $('#eu-days').textContent = days > 0 ? days.toLocaleString() : '0';
    $('#eu-lede').textContent = a.eu === 'unsure'
      ? 'You said you are undecided about the EU. If that changes, this is the date that matters.'
      : 'Machinery Regulation 2023/1230 applies from this date. A learned policy in a safety function needs a notified body.';
  }
  show('dash');
}

function route() {
  ws = load();
  if (!ws) return renderAuth();
  if (!ws.done) { step = Object.keys(ws.answers || {}).length; step = Math.min(step, QUESTIONS.length - 1); return renderQuiz(); }
  renderDash();
}

/* ── events ───────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {

  $('#auth-form').addEventListener('submit', e => {
    e.preventDefault();
    const name = $('#f-name').value.trim();
    const email = $('#f-email').value.trim();
    const err = $('#auth-err');
    if (!email || !email.includes('@')) {
      err.textContent = 'Enter an email address so the workspace has a name on it.';
      err.hidden = false; $('#f-email').focus(); return;
    }
    err.hidden = true;
    ws = { name, email, answers: {}, done: false, created: new Date().toISOString() };
    save(ws); step = 0; renderQuiz();
  });

  $('#returning-go').addEventListener('click', () => { route(); });
  $('#returning-new').addEventListener('click', () => {
    clear(); ws = null; $('#returning').hidden = true; $('#f-name').focus();
  });

  $('#quiz-opts').addEventListener('click', e => {
    const btn = e.target.closest('.opt'); if (!btn) return;
    ws.answers[QUESTIONS[step].id] = btn.dataset.v;
    save(ws);
    if (step < QUESTIONS.length - 1) { step++; renderQuiz(); }
    else { ws.done = true; save(ws); renderDash(); }
  });

  $('#quiz-back').addEventListener('click', () => { if (step > 0) { step--; renderQuiz(); } });

  $('#dash-edit').addEventListener('click', () => { ws.done = false; save(ws); step = 0; renderQuiz(); });
  $('#dash-reset').addEventListener('click', () => {
    if (!confirm('Delete this workspace from your browser? The answers cannot be recovered.')) return;
    clear(); ws = null; renderAuth();
  });

  $('#copy-yaml').addEventListener('click', async e => {
    try {
      await navigator.clipboard.writeText(yaml(ws));
      const b = e.currentTarget, was = b.textContent;
      b.textContent = 'Copied'; setTimeout(() => { b.textContent = was; }, 1400);
    } catch {}
  });

  $('#dl-yaml').addEventListener('click', () => {
    const blob = new Blob([yaml(ws)], { type: 'application/x-yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'campaign.yaml';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  route();
});
