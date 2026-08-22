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

This is **stage 01–04** of the pipeline on the website: ingest, perturb,
detect, and the provenance that makes the result mean anything. It runs one
point in the parameter space.

It is **not** the search, the failure minimiser, or the report generator.
Those are loops and aggregations over this, and building them first would have
produced results nobody could reproduce. They come next.

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
- The torso contact force is the only contact signal; per-link forces and a
  centre-of-mass-outside-support-polygon predicate are not implemented.
- `StandPolicy` is a PD hold, not a learned policy. It is a baseline: a
  perturbation that cannot topple it is not testing much.
