---
name: spatial-maths-and-frames
description: Rotations, frames and the linear algebra under robot state — rotation matrices and SO(3), why the transpose is the inverse, quaternion conventions and their ordering traps, world vs body frame, and where arccos loses precision. Use when reading or writing observation code, converting between frames, debugging a policy that behaves as though it is upside down, or checking any claim about tilt, gravity or base velocity.
metadata:
  origin: written for this repo
---

# Frames, rotations, and where they go wrong

Almost every silent bug in this harness has been a frame bug. They do not
raise. A vector in the wrong frame is still three finite floats, so the policy
consumes it, acts confidently, and the campaign reports failures that belong to
the harness rather than the robot.

The rule that prevents most of them: **a vector is meaningless without the
frame it is expressed in.** Name the frame in the variable, the comment, or
both.

## The rotation matrix

MuJoCo stores each body's orientation as a flat 9-vector:

```python
R = data.xmat[robot.base_body_id].reshape(3, 3)   # observe.py:159
```

`R` maps **body → world**. Its columns are the body's own x, y, z axes written
in world coordinates. So `R[:, 2]` is where the robot's "up" is pointing, as
the world sees it.

`R` is orthonormal — its columns are unit length and mutually perpendicular.
That gives the single most useful fact here:

> **R⁻¹ = Rᵀ.** The transpose is the inverse.

This is why the code never calls a matrix inverse. `R.T` is exact, costs
nothing, and cannot fail numerically. Anywhere you see `R.T @ v`, read it as
"take this world vector into the body frame."

## World into body: the two live examples

```python
v = R.T @ data.qvel[0:3]              # base_lin_vel   (observe.py:171)
v = R.T @ np.array([0.0, 0.0, -1.0])  # projected_gravity (observe.py:175)
```

`projected_gravity` is worth understanding properly, because it is the term
most locomotion policies actually depend on. Gravity in the world is always
straight down. Rotated into the robot's own frame, it becomes a unit vector
saying *which way is down relative to me*. Standing upright it is `[0, 0, -1]`;
tipped forward, the x-component grows. That is how a policy senses its own
attitude without any global position sensor — and why it is in
`ObservationSpec.default()` first.

## The MuJoCo trap: free-joint velocities are in different frames

For a floating base, MuJoCo's `qvel` is **not** uniformly framed:

| Slice | Quantity | Frame |
| --- | --- | --- |
| `qvel[0:3]` | linear velocity | **world** |
| `qvel[3:6]` | angular velocity | **body** |

This asymmetry is the reason the two lines above look inconsistent:

```python
elif t.kind == "base_lin_vel":
    v = R.T @ data.qvel[0:3]   # qvel[0:3] is world frame
elif t.kind == "base_ang_vel":
    v = data.qvel[3:6]         # already body frame in MuJoCo
```

Adding `R.T` to the angular case — the "consistent" thing to do — silently
double-rotates it. Nothing raises. The policy just gets a wrong turn rate.

## Quaternions

MuJoCo orders quaternions **scalar first: `(w, x, y, z)`**. SciPy's
`Rotation.as_quat()` returns **scalar last: `(x, y, z, w)`**. Most training
code uses one; the harness uses the other.

For a free joint, `qpos[0:3]` is base position and `qpos[3:7]` is the base
quaternion — which is exactly what `base_quat` reads (`observe.py:169`).

Two properties to keep in mind:

- `q` and `-q` are the same rotation. A sign flip mid-trajectory is a
  representation artefact, not motion. Never difference raw quaternions to
  estimate rotation.
- Unit norm is a constraint, not a guarantee. Integration drifts off the unit
  sphere; MuJoCo renormalises, hand-rolled code often does not.

Prefer rotation matrices or `projected_gravity` for anything a predicate reads.
Quaternions are for storage and interchange, where their compactness pays.

## Where precision is lost: arccos

```python
tilt = float(np.degrees(np.arccos(np.clip(R[2, 2], -1.0, 1.0))))  # runner.py:109
```

`R[2, 2]` is the z-component of the body's z-axis in world coordinates — the
cosine of the angle between the robot's up and the world's up. So this is tilt
from vertical, in degrees.

Two things are happening in that line, both deliberate:

**The clip is not defensive padding.** An orthonormal matrix should have
`|R[2,2]| ≤ 1`, but accumulated floating-point error puts it at `1.0000000002`
often enough to matter, and `arccos` of that is `nan`. One `nan` propagates
through the whole trajectory and the run is lost.

**`arccos` is ill-conditioned near its ends.** Its derivative is
`-1/√(1-x²)`, which blows up as `x → ±1`. Near-upright (`R[2,2] ≈ 1`) is
exactly there. A tiny error in `R[2,2]` becomes a large error in the reported
angle, so *small tilt readings are noisier than large ones*. This is fine for
this harness — the predicates fire at thresholds like 35°, far from the bad
region — but it means small-angle tilt should not be trusted to a tenth of a
degree, and a predicate thresholded at 1° would be measuring numerical noise.

## Checklist when a frame bug is suspected

1. Does the observation layout match the training code, index for index?
   `ObservationSpec.describe()` prints it; diff that, do not assume.
2. Is a `R.T` missing, or applied twice? Check against the table above.
3. Quaternion order — `(w,x,y,z)` here, `(x,y,z,w)` in SciPy.
4. Is the sign of gravity right? `projected_gravity` should read
   approximately `[0, 0, -1]` for a robot standing still and upright. If it
   reads `[0, 0, +1]`, the policy believes it is inverted.
5. Fixed base? Then there is no base motion to observe at all, and
   `ObservationSpec.validate()` refuses those terms rather than returning
   zeros (`observe.py:130–138`).

## Related

`rigid-body-dynamics` covers what `qpos`/`qvel` contain and how joints are
addressed. `robot-policy-testing` owns determinism and reproducibility.
