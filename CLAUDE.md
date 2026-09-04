# Faultline

Adversarial testing for learned robot control policies. The harness searches a
declared space of physical conditions for the ones that make a frozen policy
violate a rule the customer wrote, then hands back evidence someone hostile can
re-run.

Solo founder, pre-product, based in Baku. Python + MuJoCo harness, static site.

## Standing rules

These are not style preferences. They are the product.

1. **Never overstate what is real.** The harness finds failures; it cannot show
   their absence. Never write that a policy is safe, verified, validated,
   certified or compliant, and never imply the output satisfies a notified body
   — nobody can currently say what does.
2. **Flag every placeholder.** `hello@faultline.dev` appears across the site and
   is **invented** — it is not a real address. Say so whenever it comes up
   rather than treating it as configured.
3. **Label illustrative values as illustrative**, in the same sentence, never in
   a footnote.
4. **Trace claims to code or to a measured number.** This repo has repeatedly
   shipped numbers that drifted from the implementation. If a figure cannot be
   traced, cut it or mark it unverified.
5. **Requested is not delivered.** The impulse and sensor-lag axes quantise on
   the control grid — see `control-theory`. Quote them as requested values.
6. **Directed-search hit rates are not failure rates.** Only uniform samples
   support a rate. See `uncertainty-and-evidence`.

## Load-bearing facts

Verify before quoting; they drift.

- **7 searchable axes** — `friction_mu`, `payload_kg`, `payload_offset_m`,
  `push_impulse_ns`, `sensor_lag_ms`, `slope_deg`, `torque_loss_pct`. The
  authority is `_AXIS_BY_NAME` in `harness/faultline/space.py`. Yaw and push
  time describe *which way* and *when*, and are set on the base spec instead.
- **4 trajectory signals** — `tilt_deg`, `height_m`, `contact_force_n`,
  `joint_vel_rads`. Predicates see nothing else.
- **3 seeds, kept separate** — sampler, sim, policy. One global seed hides which
  component caused a divergence.
- **EU Machinery Regulation 2023/1230** applies from 20 January 2027; the
  delegated act defining adequate evidence is not due until 2028.

## Layout

| Path | What |
| --- | --- |
| `harness/faultline/` | the product: model loading, observation layout, runner, search, reduction, reporting |
| `harness/tests/` | the test suite — run it before claiming anything works |
| `docs/primer.md` | the domain from scratch, written to be learned from |
| `docs/strategy.md`, `product-spec.md`, `roadmap.md` | business case, spec, sequencing |
| `index.html`, `configure/`, `app/`, `start/`, `report/` | the static site |

Run the tests with `cd harness && python3 -m pytest tests/ -q`.

## Which skill covers what

Bodies load on demand; consult them rather than re-deriving.

- `spatial-maths-and-frames` — rotations, quaternions, world vs body frame
- `rigid-body-dynamics` — qpos/qvel, joints, contact, divergence
- `control-theory` — control rate, actuators, latency, quantisation
- `rl-for-robot-policies` — how policies are trained, observation contracts
- `optimisation-and-search` — severity, CEM, sampling bias
- `uncertainty-and-evidence` — what the numbers license you to claim
- `robot-policy-testing` — reproducibility, predicates, sim-to-real, regulation

## Working style

The user is learning this domain deliberately (`docs/learning-path.md`) in order
to co-engineer rather than delegate. Explain reasoning; do not just produce
output. When something is wrong, say which line and why.
