# Faultline — app brief, part two

Follow-up prompt for Figma AI. Covers the four screens not yet generated, plus
factual corrections to the two that were.

Measured values below come from real campaigns. Anything illustrative is
labelled as such.

---

## Paste from here

You have already produced two frames for **Faultline**: `campaigns-home` and
`new-campaign`. Keep their visual language exactly — same type, spacing,
density and components. This is a continuation, not a redesign.

Two jobs: correct some factual errors in the existing frames, then add the four
screens that are missing.

---

# PART 1 — Corrections to the existing frames

**`campaigns-home`**

1. The `MODES` and `DURATION` columns have collided into one header reading
   `MODESDURATION`, and their values are touching — `82h 14m` is actually
   modes `8` and duration `2h 14m`. Separate them into two columns with a gap.
2. Durations are unrealistic. A campaign of 120 simulations against a 12-joint
   quadruped takes **10.6 seconds** on one core. Scale from that: 150 sims is
   about 13 s, 1000 sims about 90 s. A large humanoid is slower, but nothing
   here should read in hours. Use one consistent format, e.g. `13s`,
   `1m 28s`, `4m 10s`.
3. The header says `23 campaigns total` above 8 rows. Make the count match the
   rows shown.
4. `SIMULATOR CONNECTED` implies a remote service. There is none — simulation
   runs on the user's own machine. Replace with a local status, e.g.
   `local runner · mujoco 3.12.0`.
5. Keep the empty state as its own separate frame rather than stacked beneath
   the populated table.

**`new-campaign`**

6. **`Terrain roughness` is not a real parameter — delete that row.** There are
   exactly seven axes and no others:
   `push_impulse_ns`, `slope_deg`, `sensor_lag_ms`, `torque_loss_pct`,
   `payload_kg`, `payload_offset_m`, `friction_mu`.
7. Show the real field name next to the human label on every axis row — an
   engineer copies these into a config file, so `Push impulse` alone is not
   enough. Show both, e.g. `Push impulse` with `push_impulse_ns` beside it.
8. **`Covariance Matrix Adaptation (CEM)` is wrong.** CEM is the
   **Cross-Entropy Method** — it fits a distribution to the most severe samples
   so far and resamples from it. Covariance Matrix Adaptation is a different
   algorithm. Label it `Cross-Entropy Method (CEM)`, with the plain description
   "concentrates budget where failures are dense". The other option is
   `Random` — "covers the declared volume uniformly".
9. `Payload offset` is shown in cm; the stored field is metres
   (`payload_offset_m`, 0–0.15). Show metres, or show both.
10. The URDF card reads `FLOOR FRICTION 0.00 μ`. A URDF carries no floor
    friction at all — showing `0.00` states something false. Display
    `not specified` for URDF, and a real value only for MJCF.
11. Add a short caution under the robot card for URDF specifically: a URDF
    carries no contact parameters and no actuator dynamics worth trusting, so
    friction, joint damping and gear ratios must be checked after conversion.

---

# PART 2 — The four missing screens

## Screen 3 — Campaign result

Opened by clicking a row in `campaigns-home`. The verdict first, then detail.

**Header strip** — one line of run identity, all measured:

```
cem · seed 41279 · budget 120 · 106 of 120 runs violated
first failure at simulation 0 · 10.6 s elapsed
```

**Failure modes — the main element of the page.**

Failures are grouped by *what they actually need* once everything irrelevant is
relaxed away. Never lead with a raw failure count: a count moves with the
budget and invites an argument, a mode is a reason. Two real modes:

```
12 ×   tilt_limit via push_impulse_ns
       minimal case    push_impulse_ns  7.96 N·s
       region          9.681 .. 15.485 N·s      median 12.656
       locally minimal  yes

 2 ×   tilt_limit via push_impulse_ns + torque_loss_pct
       minimal case    push_impulse_ns  7.16 N·s
                       torque_loss_pct  10.25 %
       region          push_impulse_ns  9.546 .. 12.655 N·s   median 11.100
                       torque_loss_pct  19.038 .. 19.082 %    median 19.060
       locally minimal  yes
```

Each mode row expands, or links to Screen 4.

**Coverage** — stated conservatively, because it is evidence:

```
36 of 64 cells visited (56.25%) at 4 bins per axis

axis                declared        sampled
push_impulse_ns     0 .. 16 N·s     0.908 .. 15.451
slope_deg           0 .. 12 deg     0.041 .. 11.98
sensor_lag_ms       0 .. 50 ms      0.2 .. 50.0
```

Include the sentence: "The campaign sampled this volume; it did not sweep it."

**Actions** — download deliverables, re-run, compare with another campaign.

## Screen 4 — Failure mode detail

One mode in full.

- The minimal reproducing case, one axis per line with its unit.
- The moment the rule fired, measured:
  `tilt_limit · tilt_deg > 35 · first fires at t = 1.26 s · value 42.23 · peak 180.00`
- A line chart of the signal over the run with the threshold drawn as a
  horizontal reference and the first crossing marked. Flat fills only, no
  gradient under the line.
- A statement of what "locally minimal" means and does not mean:
  "Relaxing any listed axis further stops the failure. A different combination
  might still be smaller." Include the probe count — `15 simulations`.
- A copyable command that re-runs this exact case.
- The axes that were tried and found irrelevant, listed as eliminated — this is
  usually the most useful thing on the page, because it tells the engineer what
  does *not* matter.

## Screen 5 — Compare checkpoints

**The most important screen in the product. Give it the most design attention.**

An engineer opens this every morning. It answers one question: **what got worse
since the last checkpoint?**

Two campaigns selected at the top, older on the left. Then four groups, in this
order of prominence:

**Widened** — a mode present in both, whose failing region grew. The policy now
fails under *milder* conditions than before. This is the subtlest and most
valuable finding, because a pass/fail count hides it completely. Real measured
example:

```
tilt_limit via push_impulse_ns + torque_loss_pct        2 → 3 failures
  push_impulse_ns    min  9.546 → 8.302 N·s      fails under weaker pushes
  torque_loss_pct    max 19.082 → 45.000 %       fails across a wider band
```

**New** — modes in the newer campaign only. *(illustrative shape, not measured)*

```
height_floor via friction_mu + slope_deg               0 → 4 failures
  minimal   friction_mu 0.31 · slope_deg 8.0 deg
```

**Fixed** — modes in the older campaign only. *(illustrative shape)*

```
tilt_limit via payload_kg + push_impulse_ns            3 → 0 failures
```

**Unchanged** — collapsed by default. Real example:

```
tilt_limit via push_impulse_ns          12 → 11 failures    region comparable
```

An overall status at the top: blocking when anything is new or widened,
passing when not.

**The refusal state matters as much as the comparison.** If the two campaigns
used different axes, different rules, or a different robot model, do not
compare them. Show a clear message naming the field that differs — a
comparison across a changed search space looks meaningful and is not.

## Screen 6 — Evidence

What a third party who does not trust the vendor would need.

Three artifacts, each downloadable:

```
engineering-report.md   failure modes, each with its smallest reproducing case
safety-appendix.md      method, every rule defined, coverage, and the limits
                        of the evidence — written for an assessor, not an author
archive/                every run's seeds, config hash, model hash and verdict,
                        plus a trajectory trace per failure mode
```

Show the archive contents as a file tree: `campaign.json`, `manifest.jsonl`,
`report.json`, `traces/mode-1.csv`.

Show one manifest record expanded, so the provenance is visible — this is real:

```
index 0 · verdict fail · severity 144.999722
config_sha256  2b8d6a09855dd02e382c075ef23d3f2bf6019a64195d05814f11b58a5b4adc37
model_sha256   18fc483cc4e0ce8115f7d837125bdd8f888f2575dce2770fc06da8f8b5b9288d
seeds          sampler 41279 · sim 0 · policy 0
perturbation   push_impulse_ns 15.451 · slope_deg 11.392 · sensor_lag_ms 21.150
violation      tilt_limit · tilt_deg > 35 · first_t 1.14 s · peak 180.00
```

Show the recorded environment:

```
mujoco 3.12.0 · numpy 2.4.6 · python 3.11.15 · Linux-x86_64
```

with the explanation: a result re-run in an identical environment must land in
the same place; a different environment may legitimately differ, which is why
the environment is recorded rather than assumed.

Include a "What this evidence does not claim" block:

```
Not a proof of safety. It finds failures; it cannot show their absence.
Only the most severe failures were reduced. The grouping is not exhaustive.
Reproducible within one simulator build and CPU architecture, not across them.
```

---

# Rules — unchanged from the first brief

- **No gradients anywhere**, including under chart lines. Flat fills only.
- No glows, glassmorphism, decorative shadows, or blurred coloured shapes.
- No emoji, no decorative icons beside headings.
- Number things only when they are a genuine sequence. The form steps are;
  the three artifacts are not.
- Every number carries its unit. Numeric columns align, tabular figures.
- Never claim a policy is safe, proven, verified, certified or compliant.
- Errors name the offending field and say how to fix it.
- Keyboard operable, visible focus, 44px targets, WCAG AA contrast.
- Keep the visual identity you already established.

## Paste to here
