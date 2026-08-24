# Faultline — product specification

The three layers from [strategy.md](strategy.md), as buildable specification.
Written against the code that exists today, naming real types and real files.

---

## Layer 1 — The gate

### What it answers

*Between this checkpoint and the last one, what got worse?*

Not "how many failures" — that number moves with the budget and the seed, and
invites an argument instead of a decision. The question is which **failure
modes** appeared, vanished, or widened.

### The key insight: the diff is set arithmetic over types we already have

`FailureMode` in `harness/faultline/report.py` groups failures by the axes
genuinely required to reproduce them, once everything irrelevant is relaxed
away:

```python
@dataclass
class FailureMode:
    predicate: str                 # which rule fired
    required: tuple[str, ...]      # which axes are actually necessary
    members: list[Sample]
    exemplar: ReductionResult      # the minimal reproducing case
```

`(predicate, required)` is already a stable composite key — a *signature*. Two
campaigns produce two sets of signatures, and the regression diff is:

```
new      = sig(B) - sig(A)
fixed    = sig(A) - sig(B)
common   = sig(A) & sig(B)      → compare region() to detect widening
```

This matters more than it looks. It means Layer 1 is a **comparison layer over
machinery that already works**, not a rewrite. The hard part — deciding what
counts as "the same failure" — was solved when reduction was built, and it was
solved *explainably*, which is why the diff can be trusted.

### Widening

For a signature present in both campaigns, `FailureMode.region(space)` gives
the box its members occupy per required axis (min / median / max). A mode has
**widened** if its box grew in any required axis — the policy fails under
conditions that previously did not break it, even though the mode is not new.

This is the subtlest and most valuable output, because it catches degradation
that a pass/fail count hides entirely.

### Output format

```
faultline diff runs/v40/report.json runs/v41/report.json
```

```
checkpoint v41 vs v40      (budget 2000, cem, seeds matched)

  NEW      tilt_limit via push_impulse_ns
           minimal: push_impulse_ns = 6.2 N·s
           → repro: faultline replay runs/v41/archive/mode-4.json

  NEW      foot_slip via friction_mu + slope_deg
           minimal: friction_mu = 0.31, slope_deg = 8.0

  WIDER    tilt_limit via push_impulse_ns + torque_loss_pct
           push_impulse_ns   min 9.1 → 6.8   (fails under weaker pushes)

  FIXED    contact_limit via payload_kg + torque_loss_pct

  4 modes, 2 new, 1 widened, 1 fixed.     BLOCKING
```

Exit codes, matching the existing CLI convention in `harness/faultline/cli.py`
(0 clean / 1 findings / 2 usage error):

- `0` — no new or widened modes
- `1` — regressions found
- `2` — campaigns not comparable

### Comparability is a hard gate

Two campaigns are only comparable if the search space, the predicates and the
robot model match. `Report.as_dict()` already records
`base_config_sha256`, `space`, and `environment` — so this is checkable, and it
must be **checked, not assumed**. Comparing across a changed space silently
produces a diff that looks meaningful and is not. That is precisely the class
of quiet wrongness this company exists to eliminate; shipping it in our own
tool would be self-refuting.

Mismatched space or predicates → exit 2, naming the field that differs.
A differing `environment` is a warning, not an error — it is legitimate drift,
and the existing `replay()` logic already draws this distinction correctly.

### What Phase A must add first

The harness runs **our** robot and **our** policies. Before any of the above is
useful to anyone else:

| Gap | Where | Note |
| --- | --- | --- |
| URDF / MJCF ingest | `spec.py` — `RunSpec.model_path`, `model_hash()` | `model_hash()` already hashes file bytes, so provenance is handled |
| ONNX / TorchScript policies | `policies.py` — the `Policy` Protocol | The seam exists: `reset(seed)` / `act(obs, t)`. This is implementing against it, not redesigning |
| Observation mapping | new | The real work. A customer's policy expects *their* observation layout; this is the adapter nobody can skip |
| Parallel execution | `search.py` | Serial today. 150 sims → 50,000 |

**Observation mapping is the sleeper task.** Model and policy loading are
plumbing. Mapping a customer's observation and action convention onto the
simulation is where integrations actually die, and it should be scoped as the
main body of Phase A rather than an afterthought.

---

## Layer 2 — The estimate

### What it answers

*What does a simulated failure rate imply about the real one?*

### Method

Prediction-powered inference, following SureSim
([arXiv:2510.04354](https://arxiv.org/abs/2510.04354)). A large simulated
campaign gives a biased but cheap estimate. A small set of **paired** sim/real
evaluations — the same conditions, run in both — measures that bias. PPI
combines them into a confidence interval that is valid even though the
simulator is wrong.

The essential property: the interval is honest about simulator error rather
than assuming it away. If sim and real disagree wildly, the interval is wide
and *says so*. That is the correct behaviour and it is the reason this layer
can be trusted.

### Interface

```python
@dataclass(frozen=True)
class Pair:
    """One condition evaluated in both places."""
    perturbation: dict[str, float]
    sim_failed: bool
    real_failed: bool

@dataclass(frozen=True)
class CalibratedEstimate:
    point: float              # bias-corrected failure-rate estimate
    lo: float                 # confidence interval
    hi: float
    confidence: float         # e.g. 0.95
    n_sim: int
    n_paired: int
    sim_only_point: float     # uncorrected, for comparison

def calibrate(campaign: CampaignResult, pairs: Sequence[Pair],
              *, confidence: float = 0.95) -> CalibratedEstimate: ...
```

`sim_only_point` is deliberately reported alongside the corrected figure. The
difference between them is the simulator's measured bias — the single most
informative number in the whole system, and one no customer has today.

### Validating this without a robot

Phase B is buildable and testable with no hardware: generate synthetic "real"
outcomes from a known ground-truth failure rate with a known sim bias, and
assert that the intervals achieve their nominal coverage over many trials.
That is standard practice for validating an estimator, and the docs must frame
it as exactly that — **estimator validated, sim-to-real gap not yet measured**.

The distinction is not pedantic. Blurring it would be the same overclaim the
product exists to prevent.

---

## Layer 3 — The evidence

### What it answers

*Can a third party who does not trust us check this?*

### What already exists

`write_archive()` and `write_deliverables()` in `report.py` already emit a
re-runnable archive, and `Report.as_dict()` records `schema_version`,
`base_config_sha256`, `environment`, coverage, and every mode with its minimal
case and a `locally_minimal` flag. Reproducibility is already the design
centre — `replay()` distinguishes a determinism bug from legitimate
environment drift.

That is an unusually strong starting position for a compliance artifact, and it
exists because reproducibility was treated as the product's core claim from the
first commit rather than bolted on.

### What Layer 3 adds

| Addition | Why |
| --- | --- |
| Calibrated interval from Layer 2 | The assessor needs a real-world claim, not a sim count |
| Predicate provenance | Which requirement or standard clause each predicate implements |
| Explicit residual risk | What was *not* searched — coverage already states this honestly |
| Signed manifest | Tamper-evidence for a third party |
| Version pinning of the archive schema | An archive must remain readable years later |

### The constraint on Phases A and B

Every schema decision made now is a schema a notified body may read in 2028.
`SCHEMA_VERSION` exists in both `search.py` and `report.py` and must be
maintained rigorously — including a documented migration path — from now on,
not from whenever Layer 3 starts.

### What Layer 3 must never claim

The existing safety appendix already refuses to assert that a policy *is safe*,
and there is a test enforcing that no affirmative safety claim appears in the
generated text. That test is a load-bearing part of the product and should be
extended, never relaxed.

Faultline provides evidence. A notified body decides. Any drift from that
position destroys the only thing the company actually sells.

---

## Sequencing summary

| Phase | Builds | Needs a customer? |
| --- | --- | --- |
| A | Model ingest, policy adapters, observation mapping, parallel execution, `faultline diff` | No — public models and policies suffice |
| B | PPI calibration, synthetic-truth validation | No — estimator validated synthetically |
| C | Evidence pack, signed manifests, first paired hardware data | **Yes** — this is where a design partner becomes the bottleneck |

Phases A and B are deliberately customer-free. That is what makes this
executable by one person starting today.
