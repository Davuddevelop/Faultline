---
name: rigid-body-dynamics
description: The physics a simulator actually integrates — generalised coordinates (qpos/qvel and why nq differs from nv), joint types and DOF addressing, mass and inertia, contact and friction models, gravity, timestep and solver stability, and how a simulation diverges. Use when reading model.py or runner.py, adding a perturbation axis, modelling a new robot, or diagnosing a run that blew up or produced impossible values.
metadata:
  origin: written for this repo
---

# Rigid-body dynamics, as this harness uses it

A simulator does one thing repeatedly: given the current state and the applied
forces, compute accelerations, integrate, repeat. Everything below is about
what "state" and "forces" actually mean, because getting the indexing wrong
produces plausible nonsense rather than an error.

## State: qpos and qvel, and why they are different lengths

The state of an articulated robot is two arrays:

- **`qpos`** (length `nq`) — configuration. Where everything is.
- **`qvel`** (length `nv`) — velocity. How fast it is changing.

The obvious assumption is `nq == nv`. It is false whenever there is a floating
base, and the reason is worth internalising:

| Joint | `qpos` | `qvel` | Why |
| --- | --- | --- | --- |
| free (floating base) | **7** | **6** | 3 position + 4 quaternion, but only 3 linear + 3 angular DOF |
| ball | **4** | **3** | quaternion again |
| hinge | 1 | 1 | one angle |
| slide | 1 | 1 | one displacement |

A quaternion needs four numbers to describe three degrees of freedom — the
extra one is removed by the unit-norm constraint. So orientation lives in a
4-dimensional storage for a 3-dimensional quantity, and `qpos` and `qvel` fall
permanently out of alignment.

**Consequence: you cannot index `qvel` with a `qpos` index.** MuJoCo stores
both maps per joint, and `model.py` captures them:

```python
qpos_adr.append(int(model.jnt_qposadr[j]))   # index into qpos
dof_adr.append(int(model.jnt_dofadr[j]))     # index into qvel
```

## The `qvel[6:]` bug — the one to remember

The runner used to read joint velocities as `data.qvel[6:]`: skip the free
joint's six DOF, take the rest. Correct for a floating-base quadruped. Wrong
for anything bolted down — a fixed-base arm has no free joint, so its first six
DOF *are* joints, and the slice silently discarded them. A 3-DOF arm returned
an empty array. No exception, just a signal that was always zero.

The fix is to use the model's own addressing:

```python
jvel_arr[k] = float(np.abs(data.qvel[robot.dof_adr]).max())   # runner.py:236
```

Generalise the lesson: **never hardcode an offset that depends on the robot's
topology.** Resolve it from the model.

## Which joints a policy can drive

`load()` in `model.py` walks every joint and keeps the drivable ones:

- **Free joints are skipped** — the floating base is not actuated. Nobody puts
  a motor between the robot and the universe.
- **Ball joints are skipped** — one actuator cannot address three rotational
  DOF. This is recorded as a note, not silently dropped.
- **Hinge and slide are kept.**

Two failure modes are refused outright rather than producing an empty campaign:
a model with no hinge or slide joints at all, and a model with `model.nu == 0`
(no `<actuator>` section — the usual state of a URDF converted straight to
MJCF).

Watch for `<default>` blocks: they contain template `<joint>` elements, so
naive XML counting reports 13 joints on a 12-joint robot.

## Mass, inertia, and the payload approximation

Three quantities per body: `body_mass`, `body_ipos` (centre of mass, in body
coordinates) and `body_inertia` (the rotational inertia). The payload axis
modifies all three (`runner.py:93–102`):

```python
com[0] = (com[0] * m0 + p.payload_offset_m * p.payload_kg) / m1
model.body_mass[torso] = m1
model.body_inertia[torso] *= m1 / m0
```

The centre-of-mass shift is exact — it is the weighted average of two masses.
**The inertia scaling is an approximation**, and should be described as one.
Scaling inertia by the mass ratio assumes the added mass is distributed like
the original body. A real payload bolted 10 cm off centre adds roughly `m·d²`
by the parallel-axis theorem, which this does not model. The direction of the
error is knowable: it **understates** rotational inertia for an offset payload,
so the simulated robot rotates more easily than the real one would.

That is acceptable for a perturbation axis whose purpose is to find failures,
but it must never be presented as a faithful payload model.

## Contact and friction

Contact is the hardest part of the physics and the largest contributor to the
sim-to-real gap. MuJoCo does not use hard constraints; it uses soft ones
parameterised by `solref` (stiffness and damping timescale) and `solimp`
(impedance curve). Defaults are rarely right for a specific robot, and they are
silently wrong — the model runs and produces smooth trajectories built on
contact behaviour that does not exist.

Friction in MuJoCo has **three** components per geom: sliding, torsional,
rolling. The friction axis varies only the first, deliberately:

```python
model.geom_friction[:, 0] = p.friction_mu   # runner.py:75
# sliding friction only; torsional and rolling keep the model's values
```

Coulomb friction (`F ≤ µN`) is itself a simplification. Real friction depends
on velocity, temperature, surface history and contact area.

## Slope by rotating gravity

The slope axis does **not** tilt the floor:

```python
model.opt.gravity[:] = GRAVITY * np.array(
    [-sin(a)*cos(yaw), -sin(a)*sin(yaw), -cos(a)])   # runner.py:83
```

Tilting the floor changes the contact geometry, so a slope run and a flat run
would differ in two ways at once. Rotating the gravity vector leaves every geom
exactly where it was, which means the only thing varying between runs is the
quantity under test. It is physically equivalent for a uniform slope, and it
makes the result attributable.

## Timestep, integration, and divergence

The physics step (`model.opt.timestep`) is far smaller than the control step.
The runner derives the ratio rather than assuming it:

```python
steps_per_ctrl = max(1, round((1.0 / spec.control_hz) / dt))   # runner.py:167
```

A too-large timestep makes stiff contacts unstable. The symptom is divergence:
velocities grow without bound until the state is `inf` or `nan`.

**MuJoCo signals instability through warning counters — it does not raise.**
Four classes are checked (`runner.py:135–143`):

- `mjWARN_BADQACC` — acceleration blew up. The usual one.
- `mjWARN_BADQVEL`, `mjWARN_BADQPOS` — velocity or position went bad.
- `mjWARN_BADCTRL` — **the dangerous one.** MuJoCo responds to a bad control by
  silently resetting it to zero. The run then stays numerically perfect and
  finishes as a *clean pass*, while the policy's actual output never reached
  the robot.

A diverged run is neither a pass nor a failure. It is an invalid measurement,
and this harness raises `SimulationDiverged` and excludes it. Recording one as
a policy failure is the worst error available: the reduction would minimise it
to "fails under no perturbation at all", which is precisely what a diverged run
looks like after reduction.

## Reading contact forces

`data.cfrc_ext` is not populated by `mj_step` alone:

```python
mujoco.mj_rnePostConstraint(model, data)   # populates cfrc_ext (runner.py:227)
tilt, height, force = _base_signals(model, data, torso_id)
```

Omit that call and the force signal reads as stale or zero — again, no error.

## Related

`spatial-maths-and-frames` covers the frames these quantities live in.
`control-theory` covers actuators and the control loop that sits on top.
