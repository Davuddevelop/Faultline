# Faultline harness

Deterministic evaluation of a learned robot control policy under perturbation.

One run in, one record out. The record is enough for someone who does not
trust you to reproduce the run.

```bash
pip install -r requirements.txt
python examples/run_one.py
pytest tests/ -q
```

## What this is, and what it deliberately is not

**All five stages** on the website — ingest, perturb, search, detect, reduce —
plus the three deliverables they feed.

```bash
python examples/run_one.py       # one run, recorded, replayed
python examples/reduce_one.py    # a five-axis failure, minimised
python examples/search_one.py    # search a space, compare methods, reduce the worst
python examples/report_one.py    # a whole campaign into the three deliverables
```

## Deliverables

`build_report()` turns a campaign into failure modes, then
`write_deliverables()` writes all three:

```
engineering-report.md      what broke, and the smallest condition that breaks it
safety-appendix.md         method, predicates, coverage, reproducibility, limits
archive/manifest.jsonl     one line per run: seeds, config hash, verdict
archive/campaign.json      every sample
archive/report.json        the modes and coverage as data
archive/traces/mode-N.csv  trajectory for each mode's minimal case
```

### Failure modes: how failures are grouped

Listing 49 failures by count tells a customer nothing and invites an argument
about the number. They have to be grouped, and the grouping has to be
explainable — the moment a black box decides what counts as the same failure,
the evidence stops being checkable.

**The signature is the reduced form**: which predicate fired, and which axes
are genuinely required once everything irrelevant is relaxed away. On the
example campaign:

```
3 failure modes from the 10 most severe of 49 failures:
  1.  5 x  tilt_limit via push_impulse_ns + torque_loss_pct
  2.  4 x  tilt_limit via push_impulse_ns
  3.  1 x  tilt_limit via payload_kg + push_impulse_ns + torque_loss_pct
```

"Fails on a push alone" and "needs a push *and* degraded actuators" are
different problems for whoever has to fix them. Two runs in one group fail for
the same reason in that sense and no other, which the report says in those
words.

Only the `max_reduce` most severe failures are minimised — reduction costs a
couple of dozen simulations each, and reducing all 49 would cost more than the
campaign did. The report states how many were reduced so the grouping is never
mistaken for exhaustive.

### Coverage is reported bluntly

Six axes at four bins each is 4096 cells. 120 simulations visited **101 of
them — 2.47%**. The appendix says the campaign *sampled* the declared volume
and did not sweep it, and that behaviour in unvisited regions is unsupported
by the evidence. A coverage number that flattered the campaign would be worse
than none.

### What the documents refuse to say

Neither document claims the policy is safe, asserts conformity with any
regulation, or presents absence of a violation as evidence of safety. There is
a test for the affirmative forms of each — `demonstrates safety`, `certifies`,
`is compliant`, `verified safe` — because that is the one property of this
output that must not regress.

## Search

Declare a space; spend a budget of simulations inside it.

```python
space = SearchSpace({"push_impulse_ns": (0, 9), "slope_deg": (0, 10), ...})
random_search(spec, policy, space, budget=150, seed=0)
cem_search(spec, policy, space, budget=150, seed=0)
```

Every sample is checked to lie inside the declared bounds, both methods spend
their budget exactly, and both are reproducible from a seed.

### Random versus directed — measured

5 seeds, 150 simulations each, on the space in `examples/search_one.py`:

| method | failures per seed | median | hit rate |
| --- | --- | --- | --- |
| random | 6, 4, 7, 5, 7 | 6 | 29/750 = **3.9%** |
| directed (CEM) | 51, 68, 63, 65, 61 | 63 | 308/750 = **41.1%** |

Mean severity per CEM round on one seed, showing it concentrating rather than
wandering: `-30.7 -> -25.7 -> -17.4 -> +14.1 -> +88.6 -> +106.6`.

**Where directed search does *not* help: finding the first failure.** First
violation landed at run 55, 4, 22, 4, 49 for random and 30, 4, 22, 4, 56 for
CEM. CEM's opening round is uniform, so it has no head start; its advantage is
in how much of the remaining budget lands on failures.

Five seeds is a description, not a significance test, and `compare()` says so
in its own summary rather than implying a winner.

### The space is the experiment

These numbers only mean something because the space was chosen by measurement.
Sampling three candidate boxes first:

| space | failure rate under uniform sampling |
| --- | --- |
| wide (push 0–40, slope 0–25 …) | 87% |
| mid | 35% |
| the one used above | 2.5% |

In the wide box random sampling finds a failure almost immediately and every
failure is a full topple, so severity carries no gradient and a comparison
there would flatter whichever method was being sold. Report the space
alongside any search result, or the result is unreadable.

### Directed search here is CEM, not a trained adversary

Cross-entropy method: fit a Gaussian to the most severe samples, resample,
repeat. Black-box, no gradients, no training run, deterministic from a seed.
The variance floor (`min_std_frac`) matters — without it the distribution
collapses onto a point after a few rounds and exploration stops.

The website says *"a trained adversary"*. This is not that. Either the copy
changes or an RL adversary becomes a later feature.

### The objective is margin, not pass/fail

`severity(traj, predicate)` is the signed distance to the threshold: positive
means fired, negative is remaining margin. A binary objective would give CEM
nothing to climb. It saturates once the robot has fully toppled — every fallen
run scores about the same — so it discriminates near the boundary rather than
deep inside the failure region.

## Reduce

A raw failing run perturbs several axes at once and is a poor bug report: the
customer cannot tell which of them mattered. `reduce_failure()` relaxes each
axis back toward nominal for as long as the failure survives.

```
axis                  original   minimal   status
push_impulse_ns             26      7.62   required
slope_deg                   14         0   eliminated
sensor_lag_ms               60         0   eliminated
torque_loss_pct             15         0   eliminated
payload_kg                 1.2         0   eliminated

evaluations 24/250   locally_minimal=True   predicate=tilt_limit
```

Five perturbations become one sentence: *it topples under a 7.6 N.s push
alone; the slope, the lag, the torque loss and the payload were irrelevant.*

**Locally minimal, not globally minimal.** No single axis of the reduced case
can be relaxed further — `test_relaxing_any_required_axis_below_the_minimum_stops_the_failure`
checks exactly that — but a different combination might be smaller overall.
The record says `locally_minimal` and means it literally. If the budget runs
out the result is marked `budget_exhausted` and `locally_minimal` is false,
because a truncated search must not be reported as a minimal case.

**It preserves one named predicate**, defaulting to the earliest violation. A
run can fire several rules; if reduction only required *some* failure it could
wander into a different failure mode and then claim to have minimised the
original.

**Reducible axes** are the seven with a magnitude: push impulse, slope, sensor
lag, torque loss, payload mass and offset, and friction. `push_time_s`,
`push_yaw_deg` and `slope_yaw_deg` are *when* and *which direction*, not *how
much*, and are held fixed.

**Friction's nominal is the model's own value**, not zero, so relaxing it can
mean moving in either direction. Which direction is adversarial is a property
of the robot, not a constant: on this model a *slippery* floor is protective,
because the quadruped slides down a slope instead of catching a foot and
tipping over.

## The claim

Any recorded run can be re-run from its record and land in the same place, bit
for bit. `tests/test_harness.py::test_recorded_run_replays_to_the_same_digest`
is that claim, checked.

Where it can legitimately differ — a different MuJoCo build, a different CPU
architecture — the record carries the environment it ran in, so `replay()`
reports whether the model or the environment also changed. A digest mismatch
with an identical model and environment is a determinism bug, and the replay
result says so in those words rather than leaving it to be argued about.

## Concepts

| Piece | What it is |
| --- | --- |
| `RunSpec` | The frozen, hashable description of one test |
| `Perturbation` | One point in the parameter space, in physical units |
| `Predicate` | A rule the customer wrote, checked over the whole trajectory |
| `Seeds` | Sampler, sim and policy seeds, kept separate on purpose |
| `Policy` | Anything with `reset(seed)` and `act(obs, t)` |
| `RunRecord` | Verdict, violations, peaks, provenance |
| `replay()` | Re-runs a record and reports whether it matched, and why not |
| `SearchSpace` | The declared volume, per-axis bounds in physical units |
| `random_search()` | Uniform coverage — the baseline |
| `cem_search()` | Directed sampling that concentrates on severe regions |
| `compare()` | Both methods across several seeds, reported per seed |
| `reduce_failure()` | Relaxes a failing case to a locally minimal one |
| `build_report()` | Groups failures into modes and measures coverage |
| `write_deliverables()` | The two documents and the archive |
| `ReductionResult` | Per-axis before/after, what was eliminated, evaluations used |

### Perturbation axes implemented

`push_impulse_ns`, `push_time_s`, `push_yaw_deg`, `friction_mu`, `slope_deg`,
`slope_yaw_deg`, `sensor_lag_ms`, `torque_loss_pct`, `payload_kg`,
`payload_offset_m`.

Terrain roughness, listed on the website, is **not** implemented.

Slope is applied by rotating gravity rather than tilting the floor, so contact
geometry is unchanged between runs and the only thing varying is the quantity
under test.

### Signals predicates can read

`tilt_deg`, `height_m`, `contact_force_n`, `joint_vel_rads`. An unknown signal
name raises rather than silently never firing.

## Why the seeds are separate

One global seed hides which component caused a divergence. With three, a
replay that differs can be attributed to the sampler, the simulator or the
policy. `test_policy_seed_actually_reaches_the_policy` exists because a seed
field that nothing reads is decoration.

## Plugging in a real policy

```python
class MyPPOPolicy:
    id = "ppo:go2:41200:<sha>"          # goes in the record

    def reset(self, seed: int) -> None:
        torch.manual_seed(seed)

    def act(self, obs: np.ndarray, t: float) -> np.ndarray:
        return self.net(torch.from_numpy(obs)).detach().numpy()
```

The `id` should identify the checkpoint by content, not by path — paths get
overwritten.

## The model

`models/quadruped.xml` is a plain 12-DOF quadruped, present so the harness is
testable without a customer's asset. Nothing in the harness is specific to it
beyond requiring a body named `torso`. Swap in a real URDF or MJCF; after any
conversion, check contact parameters, joint damping and actuator gear ratios
before trusting a result.

## Known limits

- Reproducibility is claimed **within** one MuJoCo build and CPU architecture,
  not across them.
- Reduction is locally minimal only, and costs
  `O(axes x log(range/tolerance) x passes)` full simulations — 24 runs in ~2 s
  for the five-axis example above, against a default budget of 200.
- With a stochastic policy the seed is held fixed, so reduction minimises
  against that one rollout, not against the policy's distribution.
- Search is sequential. Every run is independent, so parallelism is available
  whenever it is worth the complexity — 1500 simulations took 93 s here.
- CEM finds *dense* failure regions, not necessarily *diverse* ones. Modes are
  grouped from what the search happened to find; a mode the search never
  reached cannot appear in the report.
- Documents are Markdown. PDF rendering is not implemented.
- Trajectory traces are CSV per mode. Video per flagged run, which the website
  mentions, is not implemented.
- The torso contact force is the only contact signal; per-link forces and a
  centre-of-mass-outside-support-polygon predicate are not implemented.
- `StandPolicy` is a PD hold, not a learned policy. It is a baseline: a
  perturbation that cannot topple it is not testing much.
