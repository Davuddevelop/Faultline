/* Teeter prototype — the example workspace.

   EVERYTHING IN THIS FILE IS ILLUSTRATIVE. No company, person, checkpoint,
   runner, key or gate here exists. It is written by hand to show the shape of
   the product around the one real thing it has: the published campaign record
   (js/record.js, generated). Every panel that draws from this file carries the
   tag "example" on screen; every panel that draws from the record carries
   "record". Addresses use example.com, which is reserved for documentation. */
window.TEETER_EXAMPLE = {
  workspace: { slug: 'example-robotics', name: 'Example Robotics', plan: 'Pilot', region: 'eu-central' },
  me: { name: 'You', email: 'you@example.com', role: 'Owner' },

  /* Programs: one robot product line each, the unit of the licence.
     'standin' is the record's own robot and policy; the others are examples. */
  programs: [
    { id: 'standin', name: 'Stand-in quadruped', robot: 'quadruped', policy: 'stand', source: 'record',
      baseline: 'stand-v1', gate: 'none', note: 'The harness’s own model and its baseline stance policy. One campaign, C-0001.' },
    { id: 'q2', name: 'Q2 · walk', robot: 'q2', policy: 'q2-walk', source: 'example',
      baseline: 'v40', gate: 'blocked', note: 'A walking quadruped whose CI calls teeter gate on every checkpoint.' },
    { id: 'a7', name: 'A7 arm · pick', robot: null, policy: null, source: 'example',
      baseline: null, gate: 'setup', note: 'Waiting on manipulation signals (grasp force, drop), which are not built yet.' }
  ],

  /* Q2's checkpoints, newest first. min_push is the smallest requested push
     (N·s) under which the standard campaign found a tilt_limit failure. */
  checkpoints: [
    { id: 'v41', hash: '9c1e44a0', date: '2026-10-06', by: 'ci · PR #212', gate: 'blocked', modes: 4, min_push: 6.2, campaign: 'C-0412' },
    { id: 'v40', hash: '51b07f3d', date: '2026-09-29', by: 'ci · PR #205', gate: 'passed', modes: 3, min_push: 7.9, campaign: 'C-0405', baseline: true, shipped: true },
    { id: 'v39', hash: 'e7a2c910', date: '2026-09-22', by: 'ci · PR #199', gate: 'refused', modes: 3, min_push: 7.9, campaign: 'C-0398' },
    { id: 'v38', hash: '0f5d3b62', date: '2026-09-15', by: 'ci · PR #191', gate: 'passed', modes: 3, min_push: 7.6, campaign: 'C-0390' },
    { id: 'v37', hash: 'b2c8e015', date: '2026-09-08', by: 'ci · PR #184', gate: 'passed', modes: 4, min_push: 7.4, campaign: 'C-0381' },
    { id: 'v36', hash: '6ad4f7c8', date: '2026-09-01', by: 'manual', gate: 'passed', modes: 4, min_push: 7.1, campaign: 'C-0372' }
  ],

  campaigns: [
    { id: 'C-0413', program: 'q2', checkpoint: 'v41', method: 'cem', budget: 600, done: 212, violations: 41, modes: null, duration: null, state: 'running', runner: 'lab-gpu-02', by: 'ci', source: 'example' },
    { id: 'C-0412', program: 'q2', checkpoint: 'v41', method: 'cem', budget: 600, done: 600, violations: 233, modes: 4, duration: '41 min', state: 'blocked', runner: 'lab-gpu-02', by: 'ci', source: 'example' },
    { id: 'C-0405', program: 'q2', checkpoint: 'v40', method: 'cem', budget: 600, done: 600, violations: 188, modes: 3, duration: '39 min', state: 'passed', runner: 'lab-gpu-02', by: 'ci', source: 'example' },
    { id: 'C-0398', program: 'q2', checkpoint: 'v39', method: 'cem', budget: 600, done: 600, violations: 201, modes: 3, duration: '40 min', state: 'refused', runner: 'ci-runner-01', by: 'ci', source: 'example' },
    { id: 'C-0001', program: 'standin', checkpoint: 'stand-v1', method: 'cem', budget: null, done: null, violations: null, modes: null, duration: null, state: 'done', runner: '—', by: 'harness', source: 'record' }
  ],

  /* The gate: v41 against the shipped baseline v40, same robot hash, space,
     rules and seeds. Values are illustrative; the categories are the design. */
  gates: {
    'G-0041': {
      candidate: 'v41', baseline: 'v40', program: 'q2', verdict: 'blocked', campaign: 'C-0412', base_campaign: 'C-0405',
      match: [['robot', 'q2.xml · 3e9a…c41f', true], ['space', 'q2-standard v3', true], ['rules', 'q2-safety v2', true], ['seeds', 'sampler 0xA13F · sim 0 · policy 0', true]],
      modes: [
        { kind: 'widened', label: 'tilt_limit via push_impulse_ns', axis: 'push_impulse_ns', unit: 'N·s', before: 7.9, after: 6.2, note: 'falls at a smaller push than v40 did' },
        { kind: 'new', label: 'fallen via slope_deg + sensor_lag_ms', axis: 'slope_deg', unit: '°', before: null, after: 8.5, note: 'with sensor_lag_ms 40 requested; v40 held across the whole slope range' },
        { kind: 'fixed', label: 'tilt_limit via payload_offset_m', axis: 'payload_offset_m', unit: 'm', before: 0.052, after: null, note: 'no longer found anywhere in the declared range' },
        { kind: 'unchanged', label: 'tilt_limit via push_impulse_ns + payload_kg', axis: 'push_impulse_ns', unit: 'N·s', before: 7.4, after: 7.4, note: 'same minimal case, within tolerance 0.5' }
      ]
    },
    'G-0039': {
      candidate: 'v39', baseline: 'v38', program: 'q2', verdict: 'refused', campaign: 'C-0398', base_campaign: 'C-0390',
      match: [['robot', 'q2.xml · 3e9a…c41f', true], ['space', 'slope_deg [0, 12] against [0, 10]', false], ['rules', 'q2-safety v2', true], ['seeds', 'sampler 0xA13F · sim 0 · policy 0', true]],
      modes: []
    }
  },

  runners: [
    { name: 'lab-gpu-02', state: 'busy', host: 'linux x86_64', cores: 32, python: '3.11.15', mujoco: '3.12.0', job: 'C-0413', seen: 'now', key: 'SHA256:pV3q…8LwK', version: '0.3.0' },
    { name: 'ci-runner-01', state: 'idle', host: 'linux x86_64', cores: 16, python: '3.11.15', mujoco: '3.12.0', job: null, seen: '12 s ago', key: 'SHA256:a0Zt…Qe4m', version: '0.3.0' },
    { name: 'workstation-04', state: 'offline', host: 'darwin arm64', cores: 12, python: '3.12.4', mujoco: '3.12.0', job: null, seen: '3 days ago', key: 'SHA256:Lk7d…1rTc', version: '0.2.9' }
  ],

  members: [
    { name: 'You', email: 'you@example.com', role: 'Owner', seen: 'now', via: 'Google' },
    { name: 'Controls lead', email: 'controls@example.com', role: 'Admin', seen: '2 h ago', via: 'GitHub' },
    { name: 'RL engineer', email: 'rl@example.com', role: 'Engineer', seen: '20 min ago', via: 'GitHub' },
    { name: 'Safety lead', email: 'safety@example.com', role: 'Engineer', seen: 'yesterday', via: 'Email link' },
    { name: 'Product manager', email: 'pm@example.com', role: 'Viewer', seen: 'last week', via: 'Google' },
    { name: 'External assessor', email: 'assessor@example.org', role: 'Assessor', seen: 'never', via: 'Share link · EP-0002' }
  ],

  keys: [
    { name: 'q2 · GitHub Actions', scope: 'program q2 · gate', prefix: 'tt_live_q2_…4f1c', used: '3 min ago', by: 'Controls lead' },
    { name: 'nightly sweep', scope: 'program q2 · campaigns', prefix: 'tt_live_q2_…a90e', used: '9 h ago', by: 'RL engineer' }
  ],

  webhooks: [
    { at: '2026-10-06 18:42', event: 'gate.blocked', target: 'GitHub · PR #212', status: 200 },
    { at: '2026-10-06 18:42', event: 'gate.blocked', target: 'Slack · #q2-releases', status: 200 },
    { at: '2026-09-29 11:05', event: 'gate.passed', target: 'GitHub · PR #205', status: 200 },
    { at: '2026-09-22 16:20', event: 'gate.refused', target: 'GitHub · PR #199', status: 200 }
  ],

  audit: [
    { at: '2026-10-07 09:14', who: 'you@example.com', what: 'shared evidence pack EP-0002 with assessor@example.org (expires 2026-11-07)', from: 'web' },
    { at: '2026-10-06 18:42', who: 'runner lab-gpu-02', what: 'completed campaign C-0412 (600 evaluations, signed)', from: 'runner' },
    { at: '2026-10-06 18:01', who: 'api key q2 · GitHub Actions', what: 'started gate G-0041 for q2 v41', from: 'api' },
    { at: '2026-10-02 10:30', who: 'controls@example.com', what: 'issued runner token for ci-runner-01', from: 'web' },
    { at: '2026-09-29 11:06', who: 'rl@example.com', what: 'set q2 baseline to v40 (shipped)', from: 'web' },
    { at: '2026-09-20 15:12', who: 'controls@example.com', what: 'changed space q2-standard v2 → v3 (slope_deg upper 10 → 12)', from: 'web' }
  ],

  evidence: [
    { id: 'EP-0001', program: 'standin', release: 'stand-v1', campaigns: ['C-0001'], state: 'draft', signed: false, shared: null, source: 'record' },
    { id: 'EP-0002', program: 'q2', release: 'v40', campaigns: ['C-0405'], state: 'shared', signed: true, shared: 'assessor@example.org · until 2026-11-07', source: 'example' }
  ],

  library: {
    spaces: [
      { id: 'standin-published', version: 1, source: 'record', used: ['Stand-in quadruped'] },
      { id: 'q2-standard', version: 3, source: 'example', used: ['Q2 · walk'] }
    ],
    rules: [
      { id: 'standin-published', version: 1, source: 'record', used: ['Stand-in quadruped'] },
      { id: 'q2-safety', version: 2, source: 'example', used: ['Q2 · walk'] }
    ]
  }
};
