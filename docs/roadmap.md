# Faultline — roadmap

Execution plan for [strategy.md](strategy.md) / [product-spec.md](product-spec.md).

**Constraint this is built around:** one person, no design partner activated
yet, product-first rather than fundraise-first. Phases A and B are therefore
deliberately ordered so that **neither requires a customer**.

---

## Phase A — "Someone else's robot" (~90 days)

The single thing between the harness and being usable by anyone. Today the
robot, the policies and the scale are all ours.

### A1. Model ingest

Load real robot descriptions, not just `harness/models/quadruped.xml`.

- URDF → MJCF conversion path, with the conversion recorded in the run record
  (a converted model is not the original, and a report that hides this is
  worthless).
- `RunSpec.model_hash()` in `spec.py` already hashes file bytes — extend to
  record *both* source and converted hashes.
- Validate joint/actuator counts against the policy's expectations at load
  time, with an error that names the mismatch.

### A2. Policy adapters

`policies.py` defines the seam already:

```python
class Policy(Protocol):
    def reset(self, seed: int) -> None: ...
    def act(self, obs: np.ndarray, t: float) -> np.ndarray: ...
```

- `OnnxPolicy` and `TorchScriptPolicy` implementing it.
- Extend `load_policy()` in `config.py` — it already supports `"stand"` and
  `"module:Attr"`; add `"onnx:path"` / `"torchscript:path"`.
- Determinism check on load: same input twice → same action, else fail loudly.
  A nondeterministic policy invalidates every downstream claim.

### A3. Observation mapping — *the real work*

A customer's policy expects their observation layout, in their units, in their
frame. This is where robotics integrations actually die.

- Declarative observation spec in `campaign.yaml` (ordered fields, units,
  frames).
- Builder that assembles the observation vector from MuJoCo state.
- Round-trip test: a known state produces the expected vector.

Budget the majority of Phase A here. A1 and A2 are plumbing; A3 is the
integration.

### A4. Parallel execution

`search.py` runs serially. 150 sims must become 50,000.

- Process-pool execution of independent samples first — simplest thing that
  works, and MuJoCo releases the GIL.
- **Determinism must survive parallelism.** Per-sample seeding already exists
  via `Seeds`; add a test asserting a parallel campaign is bit-identical to the
  serial one with the same seed. Non-negotiable — the reproducibility claim is
  the product.
- MuJoCo Warp / Newton backend later, if the process pool becomes the ceiling.

### A5. `faultline diff` — the product surface

Per [product-spec.md](product-spec.md) Layer 1.

- `diff.py`: load two `report.json`, key modes by `(predicate, required_axes)`,
  compute new / fixed / widened.
- Comparability gate on `base_config_sha256`, `space`, predicates → exit 2 on
  mismatch, naming the differing field.
- `faultline diff A B` subcommand in `cli.py`; exit 0 / 1 / 2.
- Tests: new mode, fixed mode, widened region, incomparable campaigns,
  identical campaigns diff empty.

### A6. The proof artifact

Run the whole thing end to end against a **public** humanoid or quadruped with
a **public** trained policy. Publish it the way `/report/` was published —
generated from real output, no mock-ups.

This is the demo that earns meetings. Without it, Phase C outreach has nothing
to point at.

**Phase A is done when** someone who is not us can point Faultline at their own
robot and policy, run a campaign, and diff two checkpoints.

---

## Phase B — Calibration (~90 days after A)

Per [product-spec.md](product-spec.md) Layer 2. The answer to *"so what, your
simulator is wrong."*

### B1. PPI estimator

- `calibrate.py`: `Pair`, `CalibratedEstimate`, `calibrate()`.
- Follow SureSim ([arXiv:2510.04354](https://arxiv.org/abs/2510.04354)).
- Report `sim_only_point` alongside the corrected estimate — their difference
  is the measured simulator bias.

### B2. Synthetic-truth validation

No hardware needed:

- Generate synthetic "real" outcomes from known ground truth with known sim
  bias.
- Assert nominal coverage over many trials (a 95% interval must contain truth
  ~95% of the time).
- Assert intervals widen correctly as sim/real disagreement grows.

Document precisely what this establishes: **the estimator is validated; the
sim-to-real gap is not yet measured.** Those are different claims and
conflating them would be the exact overclaim this product exists to prevent.

### B3. Archive integration

Extend `write_archive()` / `write_deliverables()` in `report.py` to record
pairs, estimate and interval. Bump `SCHEMA_VERSION` with a documented
migration.

**Phase B is done when** a campaign emits a calibrated interval, the estimator
is shown correct on synthetic ground truth, and the docs are unambiguous about
what has and has not been demonstrated.

---

## Phase C — Evidence and first partner (months ~7–12)

The first phase that **requires a customer**.

### C1. Evidence pack

Predicate provenance, explicit residual risk, signed manifest, schema version
pinning. Extend — never relax — the existing test forbidding affirmative safety
claims in generated text.

### C2. Activate design partners

Approach with: a working tool, a public proof artifact, and a calibrated
method. Ask for one robot program and paired sim/real data rights.

### C3. The artifact that matters

> A failure mode found in a real customer's policy, that they did not know
> about, which they then reproduced on hardware.

Everything above exists to make that sentence true.

### C4. Run in parallel with C1–C3

- **Co-founder / advisor with robotics or controls depth.** Does not block
  A or B; materially changes C. Start early precisely because the plan does not
  depend on it.
- **EU entity**, if Layer 3 is to be sellable into EU conformity assessment.
  Not urgent — the failure mode is letting it become urgent unnoticed.

---

## Explicitly not doing yet

| Not doing | Why |
| --- | --- |
| Hosted service, accounts, dashboard | Layer 1 infrastructure. Comes after A proves it works on a robot that is not ours |
| Building a simulator | Unwinnable against a free one. We drive theirs harder |
| Pitch deck | Product-first by choice. A deck before the C3 artifact is a narrative around a gap |
| World models / learned simulators | Active research. Adopt when published methods stabilise; do not fund the research |
| Manipulation | Locomotion and stability first. One robot class done properly beats two done partly |

---

## Order of operations, compressed

```
A3 observation mapping  ─┐
A1 model ingest         ─┼─→ A6 public proof ─→ C2 partner outreach
A2 policy adapters      ─┘         │
A4 parallel execution ────────────┤
A5 faultline diff ────────────────┘
                                   │
B1 PPI ─→ B2 synthetic validation ─┴─→ B3 archive ─→ C1 evidence ─→ C3 the artifact
```

A3 is the critical path. Start there.
