---
name: control-theory
description: The control loop between a policy and a robot — control rate vs physics rate, zero-order hold, actuator models and torque limits, sensor latency, and the quantisation errors that appear when a continuous axis is applied on a discrete control grid. Use when reading runner.py, adding or interpreting a perturbation axis, choosing a control rate, or explaining why a requested perturbation value is not the value the robot received.
metadata:
  origin: written for this repo
---

# The control loop

A policy does not touch the robot. It writes into `data.ctrl`, and the
simulator turns that into forces. Everything below is about what happens in
between, and about the places where a number you asked for is not the number
the robot got.

## Two clocks

The physics runs far faster than the policy:

```python
dt = model.opt.timestep                                  # 0.002 s typical
steps_per_ctrl = max(1, round((1.0 / spec.control_hz) / dt))   # runner.py:167
n_ctrl = int(spec.duration_s * spec.control_hz)
```

At the defaults — `control_hz = 50.0`, `timestep = 0.002` — the policy runs
once per **10 physics steps**. The action is written once and held constant
across all ten. That is a **zero-order hold**, and it is the standard
arrangement: policies are trained at a fixed rate, and running the network
every physics step would both waste compute and change the dynamics the policy
learned against.

Two consequences follow, and both matter:

**Effective delay.** A piecewise-constant control is on average half a control
period stale — 10 ms at 50 Hz — before any sensor latency is added.

**A hard reaction limit.** A 50 Hz loop can only respond to phenomena below
25 Hz (Nyquist). Contact transients are far faster than that. A policy
*cannot* react within an impact; it can only respond to the aftermath. When a
campaign shows a policy failing on a sharp push, check whether the failure is
"the policy is bad" or "no controller at this rate could have responded" —
those are different findings, and only the first is the customer's bug.

## Actuators

The harness writes the policy's raw output straight into `data.ctrl`:

```python
data.ctrl[:] = action    # runner.py:209
```

What that *means* is the model's business, not the harness's. Depending on the
`<actuator>` declared in the MJCF, the same number is a target position, a
target velocity, or a torque. This is a frequent source of confusion when a
policy trained against one convention is run against a model built with
another: nothing raises, the robot just behaves strangely.

Most locomotion policies output **target joint positions**, which a PD
controller converts to torque. The gains then dominate behaviour, and they live
in the model rather than the policy.

The torque-loss axis scales two things together:

```python
model.actuator_forcerange *= 1.0 - p.torque_loss_pct / 100.0
model.actuator_gainprm[:, 0] *= 1.0 - p.torque_loss_pct / 100.0   # runner.py:90–91
```

Both, deliberately. Cutting `forcerange` alone caps peak torque but leaves the
controller just as eager, so it saturates instead of weakening. Cutting the
gain alone weakens the response but leaves the ceiling intact. A genuinely
weaker actuator is both, so both are scaled.

## Sensor lag, and its quantisation

Latency is modelled as a ring of past observations; the policy is handed a
stale one:

```python
lag_steps = max(0, round((p.sensor_lag_ms / 1000.0) * spec.control_hz))  # runner.py:171
seen = obs_history[max(0, len(obs_history) - 1 - lag_steps)]
```

Lag is therefore quantised to whole control steps — **20 ms granularity at
50 Hz**. Combined with Python's banker's rounding, the axis behaves as a
staircase, and not a monotone one. Measured:

| Requested | Actual |
| --- | --- |
| 10 ms | **0 ms** |
| 20 ms | 20 ms |
| 30 ms | **40 ms** |
| 40 ms | 40 ms |
| 50 ms | **40 ms** |
| 60 ms | 60 ms |
| 80 ms | 80 ms |

An axis declared `sensor_lag_ms: [0, 80]` has exactly five distinct behaviours,
not a continuum. Report the achieved lag, never assume the requested value was
applied, and treat a reduced minimal case of "fails at 30 ms" as meaning 40 ms.

## Push impulse, and its quantisation

An instantaneous impulse is a delta function and would destabilise the solver,
so it is spread over a fixed window:

```python
push_window = 0.05   # s
mag = p.push_impulse_ns / push_window                   # runner.py:180
in_push = p.push_time_s <= t < p.push_time_s + push_window
data.xfrc_applied[torso_id] = push_force if in_push else 0.0
```

The window is 0.05 s but the test `in_push` is evaluated on the **control
grid**, at 0.02 s spacing. Whether 2 or 3 control steps fall inside the window
depends on where `push_time_s` sits relative to that grid, and the force is
held for a whole control step either way. So the delivered impulse is not the
requested one:

| `push_time_s` | Steps in window | Requested | **Delivered** |
| --- | --- | --- | --- |
| 1.0 (the default) | 3 | 10 N·s | **12 N·s** |
| 0.005 | 2 | 10 N·s | **8 N·s** |

**At the default push time, every impulse over-delivers by 20%.** The axis is
labelled in N·s and does not deliver those N·s.

This is a known, unfixed limitation, and it has a direct consequence for how
results are written: a reduced minimal case reported as "7.96 N·s" is a
*requested* value, and the robot actually received about 9.55 N·s at default
timing. Do not quote impulse figures to three significant figures as though
they were delivered quantities, and say "requested" when quoting them at all.

The general lesson, and the reason both of these are worth documenting: **a
continuous axis applied on a discrete grid is not continuous.** Any axis whose
effect is gated by a time comparison against the control clock will quantise.
Check new axes for this before trusting their units.

## Choosing a control rate

- Match the rate the policy was trained at. A policy trained at 50 Hz and run
  at 100 Hz sees its own action history at the wrong cadence.
- `steps_per_ctrl` must come out ≥ 1. A control rate faster than the physics
  rate silently clamps to 1 via the `max(1, ...)`, and the loop then runs
  slower than requested.
- Raising the control rate shrinks the quantisation errors above but does not
  remove them.

## Related

`rigid-body-dynamics` covers the physics being controlled and how it diverges.
`rl-for-robot-policies` covers where the policy's action comes from.
