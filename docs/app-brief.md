# Faultline — app build brief

A prompt for generating the product application (not the marketing site).
Everything below is real: the field names, units, signals and example values
are taken from the working harness, not invented.

---

## Paste from here

Build a web application called **Faultline**.

### What the product does

Robotics companies ship robots controlled by *learned policies* — neural
networks that read sensors and drive motors. Nobody can tell in advance which
real-world conditions make one fail. Faultline searches simulated conditions
adversarially to find those failures, reduces each one to the smallest
condition that still causes it, and produces evidence a third-party auditor
can re-run.

The user is a robotics engineer. They are technical, sceptical, and time-poor.
They care about one question above all: **what changed since my last
checkpoint?**

This is an operational tool, not a marketing page. It is scanned and operated,
not read.

---

### Screens

**1 — Campaigns (home)**
A list of past campaigns, newest first. Each row: robot name, policy name or
checkpoint id, method, budget, failure count, number of distinct failure
modes, duration, timestamp, and a pass/fail verdict. Filter by robot and by
verdict. Clicking a row opens it.

Empty state: no campaigns yet, with a single action to start one.

**2 — New campaign**
A form in five parts. It must be valid on load, with sensible defaults, so a
user can start without filling anything in.

- *Robot* — a file drop for `.urdf` / `.mjcf` / `.xml`. Once read, show what
  was found: format, moving joints, actuators, bodies, free joints, floor
  friction, and a SHA-256 of the file. A CAD file (`.step`, `.sldprt`,
  `.iges`, `.f3d`) must be refused with an explanation: CAD carries geometry
  but not joint axes, masses or inertias, so it cannot be simulated; the user
  needs to export URDF from their CAD tool first.
- *Policy* — either a built-in baseline controller, or the user's own,
  referenced as `module:ClassName`.
- *What to vary* — the seven axes below, each toggleable, each with a
  from/to range in its real physical unit. Never normalise to 0–1; an
  engineer needs to see `slope_deg = 18`, not `slope = 0.72`.
- *What counts as failure* — repeatable rows building rules from the four
  signals below, a comparison (`>` or `<`), a threshold, and a grace period in
  seconds. Show each rule back as a plain sentence, e.g. "Fails when the body
  tilts more than 35°, ignoring the first 0.3 s."
- *How hard to look* — method (`random` or `cem`), budget in simulations,
  run length in seconds, and a random seed. Show an estimated wall-clock time.

Validation names the offending field and blocks submission until fixed.

**3 — Campaign result**
The verdict first, then the detail.

- A summary line: method, seed, budget, how many runs violated, which
  simulation the first failure appeared at, elapsed time.
- **Failure modes** — the most important element on the page. Failures are
  grouped by *what they actually need*, not listed individually. Each mode
  shows: how many failures it covers, which rule fired, which axes are truly
  required, the minimal reproducing case, and the region of the space the mode
  occupies (min / median / max per required axis).
- **Coverage** — how much of the declared space was actually sampled, stated
  conservatively. Show cells visited out of cells total, and per-axis declared
  range against sampled range.
- Actions: download the deliverables, re-run, or compare against another
  campaign.

**4 — Failure mode detail**
One mode in full. The minimal case with each axis and unit. The exact moment
the rule fired (time, the signal's value at that moment, and its peak). A line
chart of the trajectory over time with the threshold marked. A note stating
whether the case is *locally minimal* and what that does and does not mean. A
command that re-runs this exact case.

**5 — Compare checkpoints** *(the most valuable screen — give it real weight)*
Two campaigns side by side, answering only: **what got worse?**

Four groups:
- **New** — failure modes present in the second and absent in the first
- **Widened** — modes in both, where the failing region grew, meaning the
  policy now fails under milder conditions than before
- **Fixed** — modes in the first, absent in the second
- **Unchanged**

Each entry shows the mode label and, for widened modes, the before and after
values with the direction of change. A blocking/passing status overall.

If the two campaigns used different search spaces, rules, or robot models,
refuse to compare and say which field differs — a comparison across a changed
space looks meaningful and is not.

**6 — Evidence**
Three downloadable artifacts per campaign: an engineering report, a
safety-case appendix, and a re-runnable archive. Show the recorded environment
(simulator version, numeric library version, language version, platform) and
explain that a result re-run in an identical environment must land in the same
place, while a different environment may legitimately differ.

---

### The exact vocabulary — use these names and units

The seven searchable axes:

| field | unit | plain meaning |
|---|---|---|
| `push_impulse_ns` | N·s | a shove delivered to the body |
| `slope_deg` | deg | how steep the ground is |
| `sensor_lag_ms` | ms | how late the policy sees the world |
| `torque_loss_pct` | % | strength lost in the motors |
| `payload_kg` | kg | extra mass carried |
| `payload_offset_m` | m | how far off-centre that mass sits |
| `friction_mu` | – | floor friction |

The four measurable signals — rules may only be written against these:
`tilt_deg`, `height_m`, `contact_force_n`, `joint_vel_rads`.

Search methods: `random` (uniform coverage) and `cem` (directed — concentrates
budget where failures are dense).

---

### Real data to populate the interface

Use this so the app looks like a working system, not a wireframe.

A completed campaign:

```
method cem · seed 41279 · budget 120 · 106 of 120 runs violated
first failure at simulation 0 · 10.6 s elapsed
coverage 36 of 64 cells (56.25%) at 4 bins per axis
```

A failure mode, in full:

```
tilt_limit via push_impulse_ns          12 failures
  minimal case   push_impulse_ns  7.88 N·s
  fires at       t = 1.26 s
  region         push_impulse_ns  9.303 .. 14.151   median 10.674 N·s
  locally minimal: true (15 simulations)
```

A violation record:

```
predicate tilt_limit · signal tilt_deg · op ">" · threshold 35
first_t 1.14 s · value at first_t 42.23 · peak 180.00
```

The recorded environment:

```
mujoco 3.12.0 · numpy 2.4.6 · python 3.11.15 · Linux-x86_64
```

Other real mode labels for lists:
`tilt_limit via push_impulse_ns + torque_loss_pct`,
`tilt_limit via payload_kg + push_impulse_ns + torque_loss_pct`,
`height_floor via friction_mu + slope_deg`.

Method comparison, measured across 5 seeds × 150 simulations:
random found failures in 3.9% of samples; directed found 41.1%.

Robot models for a list: `quadruped_12dof.xml` (12 joints, 12 actuators,
floor friction 0.9), `atlas_arm.urdf`, `warehouse_amr.urdf`.
Checkpoints: `walk-v40`, `walk-v41`, `walk-v42`.

---

### Language rules

- Say what a thing *is*, in the engineer's words. A "campaign" is a campaign,
  a "failure mode" is a failure mode.
- Failure counts are never the headline; failure *modes* are. A count moves
  with the budget and invites an argument. A mode is a reason.
- Never claim a policy is safe, proven, verified, certified or compliant. The
  product finds failures; it cannot show their absence. Where a summary is
  needed, state what was tested and what was found.
- Every number carries its unit.
- Errors name the offending field and say how to fix it.
- No exclamation marks, no congratulatory messages, no emoji in the interface.

---

### Build rules

- **No gradients anywhere** — not in backgrounds, buttons, cards, headers or
  charts. Flat fills only.
- No glows, no glassmorphism, no drop shadows used as decoration, no blurred
  coloured orbs, no animated background effects.
- No decorative iconography beside headings, and no emoji as section markers.
- Do not number things that are not a sequence. Steps in a form are a
  sequence; a list of artifacts is not.
- Structural elements — labels, dividers, badges — must encode real
  information. If a device carries no meaning, remove it.
- Restraint over ornament. Motion only where it clarifies a state change.
- Numeric columns align; digits use tabular figures.
- Wide content scrolls inside its own container; the page never scrolls
  sideways.
- Keyboard operable throughout, visible focus states, targets at least 44px,
  and text contrast meeting WCAG AA.
- Choose your own visual identity — palette, type and layout are yours to
  decide. Make it look like a serious engineering product a robotics team
  would trust with safety evidence. Avoid the generic AI-generated look:
  no purple-to-blue, no lone acid accent on near-black, nothing that could be
  any SaaS dashboard.

### Out of scope

There is no hosted backend. Simulation runs on the user's own machine, so the
app is a front end over local results — do not build sign-up, billing, or
anything implying a cloud service that executes runs.

## Paste to here
