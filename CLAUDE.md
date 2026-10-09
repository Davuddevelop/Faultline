# Faultline

Adversarial testing for learned robot control policies. The harness searches a
declared space of physical conditions for the ones that make a frozen policy
violate a rule the customer wrote, then hands back evidence someone hostile can
re-run.

The company is **Teeter**; the engine and its CLI keep the working name
`faultline` until renamed, while the control plane and runner built on it are
`teeter-api` and `teeter`. Solo founder, pre-product, based in Baku. Python +
MuJoCo harness, a FastAPI control plane and runner (v0), static site.

## Standing rules

These are not style preferences. They are the product.

1. **Never overstate what is real.** The harness finds failures; it cannot show
   their absence. Never write that a policy is safe, verified, validated,
   certified or compliant, and never imply the output satisfies a notified body
   — nobody can currently say what does.
2. **Flag every placeholder.** `hello@teeter.dev` (the Teeter site) and
   `hello@faultline.dev` (the older pages) are **invented** — neither is a real
   address, and teeter.dev is not registered to us. Say so whenever one comes
   up rather than treating it as configured.
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
| `api/` | the control plane (`teeter-api`): FastAPI on Postgres, the job queue, gates, the app served live; see `api/README.md` |
| `runner/` | the runner and the `teeter` CLI: claims campaigns, runs the engine on the customer's machine, streams results back; see `runner/README.md` |
| `scripts/dev.sh`, `Makefile`, `docker-compose.yml` | the whole product locally, natively or in Docker; `make test` runs every suite |
| `.github/workflows/ci.yml` | CI: the three suites (the API's on Postgres too), the record check, the stack with a gate |
| `docs/primer.md` | the domain from scratch, written to be learned from |
| `docs/strategy.md`, `product-spec.md`, `roadmap.md` | business case, spec, sequencing |
| `docs/v1-roadmap.md` | engineering roadmap: architecture, v0 as built, milestones to v1 |
| `docs/product-plan.md` | the product: architecture, every screen, sign-in, what cannot be copied, build phases |
| `tools/publish_campaign.py` | re-makes the published campaign record from the engine; `--check` compares |
| `teeter/` | the Teeter website, filled by `tools/build_teeter_site.py` from the campaign record |
| `teeter/app/` | the app: every screen in `docs/product-plan.md`. Served by the API, `js/live.js` runs it on the workspace's data; anywhere else it is the prototype, record panels from `tools/build_teeter_app.py`, the rest from `js/example.js` (illustrative, tagged on screen) |
| `teeter/brand/` | the identity standard (TT-000 to TT-010) and every logo file, drawn by `tools/build_brand.py` |
| `index.html` | the front page: generated from `teeter/index.html` by `tools/build_teeter_site.py`; never edit it directly |
| `faultline.html`, `ink/`, `configure/`, `app/`, `start/`, `report/` | the older site, still under the previous identity; `faultline.html` was the front page |

Run the tests with `make test` (all three suites), or one at a time:
`cd harness && python3 -m pytest tests/ -q`, likewise in `api/` and `runner/`.

## Which skill covers what

Bodies load on demand; consult them rather than re-deriving.

- `spatial-maths-and-frames` — rotations, quaternions, world vs body frame
- `rigid-body-dynamics` — qpos/qvel, joints, contact, divergence
- `control-theory` — control rate, actuators, latency, quantisation
- `rl-for-robot-policies` — how policies are trained, observation contracts
- `optimisation-and-search` — severity, CEM, sampling bias
- `uncertainty-and-evidence` — what the numbers license you to claim
- `robot-policy-testing` — reproducibility, predicates, sim-to-real, regulation
- `teeter-brand` — the mark, tone, hatching, type, drawing conventions, voice

## Working style

**Keep replies short.** A few sentences. No headings, no bullet summaries of work
already done, no recaps of what was just built. The artifact or the diff is the
deliverable; the message is only a pointer to it.

**Ask instead of explaining.** When something is unclear, blocked, or wrong, put
the question directly and stop. Do not pre-empt it with paragraphs of context.

The user is learning this domain deliberately (`docs/learning-path.md`) to
co-engineer rather than delegate — so when something is wrong, name the line and
the reason, in one sentence.
