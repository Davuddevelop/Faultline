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

This is **stages 01–05** of the pipeline on the website: ingest, perturb,
detect, the provenance that makes a result mean anything, and reduce.

It is **not** the search or the report generator. Those are a loop and an
aggregation over this, and building them first would have produced results
nobody could reproduce.

```bash
python examples/run_one.py       # one run, recorded, replayed
python examples/reduce_one.py    # a five-axis failure, minimised
```

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
| `reduce_failure()` | Relaxes a failing case to a locally minimal one |
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
- The torso contact force is the only contact signal; per-link forces and a
  centre-of-mass-outside-support-polygon predicate are not implemented.
- `StandPolicy` is a PD hold, not a learned policy. It is a baseline: a
  perturbation that cannot topple it is not testing much.
