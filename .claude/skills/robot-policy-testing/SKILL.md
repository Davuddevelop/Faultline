---
name: robot-policy-testing
description: Conventions for adversarially testing learned robot control policies in simulation — determinism and reproducibility, robot model formats (URDF/MJCF), perturbation axes, explicit violation predicates, failure minimisation, and the sim-to-real gap. Use when working on the Faultline harness, writing or reviewing simulation/evaluation code, defining what counts as a failure, or discussing evidence a notified body would accept.
metadata:
  origin: written for this repo
---

# Testing learned robot policies

Faultline searches for the conditions under which a trained policy fails, and
hands back evidence someone else can re-run. Everything below serves that: a
result nobody can reproduce is not evidence.

## Reproducibility is the product

A campaign is worthless if a run cannot be reproduced a year later by someone
who does not trust you. Record, for every run:

- **Seed** — for the sampler, the simulator, and the policy if it is stochastic.
  Three separate seeds, recorded separately. One global seed hides which
  component caused a divergence.
- **Simulator version, pinned exactly** (`mujoco==3.1.6`, not `>=3.1`). Physics
  changes between minor versions; contact solvers especially.
- **Policy hash** — of the checkpoint file, not the path. Paths get overwritten.
- **The full resolved config**, after defaults are applied, not the config the
  user wrote.

Determinism caveats to state honestly rather than paper over: floating-point
results can differ across CPU architectures, across GPU/CPU execution, and with
threading enabled. Fix the thread count, and if a campaign must be
bit-reproducible, say on which platform.

## Robot models

- **URDF** describes kinematics and inertias. It carries no contact parameters,
  no solver settings, and no actuator dynamics worth trusting.
- **MJCF** carries what MuJoCo actually simulates. A URDF→MJCF conversion is a
  starting point, never a finished model.
- After any conversion, check: contact `solref`/`solimp`, friction (sliding,
  torsional, rolling), joint damping and armature, actuator gear ratios and
  torque limits. Defaults here are silently wrong and produce a policy that
  passes in simulation for reasons that do not exist on hardware.
- Ask which parts of the model the customer actually trusts. Usually they trust
  the link geometry and distrust the contact and actuator models — and those
  are the two that dominate the reality gap.

## Perturbation axes

Each test is one point in a declared parameter space. Keep axes physical and
named in units, never normalised to 0–1 in the interface — a reviewer needs to
read `slope: 18 deg`, not `slope: 0.72`.

Axes worth supporting: push impulse (N·s), ground friction µ, slope (deg),
terrain roughness (cm RMS), sensor latency (ms), actuator torque loss (%),
payload mass (kg) and offset (cm), and observation noise.

**Axes combine.** Single-axis sweeps find the failures the customer already
knows about. The interesting violations sit in corners — moderate slope *and*
moderate latency *and* a payload slightly off centre, none individually
alarming. Do not report single-axis results as if they were coverage.

## Violation predicates

A failure is a rule the customer wrote. Never a learned classifier, never a
heuristic we invented. When a run is flagged, the customer must be able to read
the line that flagged it and disagree with it.

- Predicates are explicit functions over the trajectory: `tilt(t) > θ_max`,
  `contact_force(t, link) > F_max`, `com(t) ∉ S_safe`, recovery not reached
  within `t_recover`.
- Evaluate over the whole trajectory, not just the final state. A policy that
  violates a limit at t=3 s and recovers by t=6 s has still violated it.
- Record *which* predicate fired and at what time, not just that the run failed.
- Watch for predicates that can never fire given the simulated ranges — a
  predicate with zero activations across a campaign is usually a bug in the
  threshold or the units, not evidence of safety.

## Minimise every failing case

A raw failing run is a bad bug report: it perturbs eight axes at once and the
customer cannot tell which mattered. Reduce it — relax perturbations toward
nominal until the violation stops firing, and report the smallest condition
that still breaks the policy.

Reduce along one axis at a time and re-run; do not assume the axes are
independent. Report the reduced case *and* keep the original run in the
archive.

## Clustering, not counting

"1,247 failures" tells a customer nothing and invites them to argue with the
number. Cluster by failure mode and report the region of parameter space each
cluster occupies. Three named modes with boundaries beat a four-digit count.

## The sim-to-real gap

State it, do not hide it. A simulated failure is a hypothesis about hardware
until the robot reproduces it.

- Contact and friction modelling is the dominant error source, followed by
  actuator dynamics (torque-speed curves, gearbox friction, control latency).
- A failure found in simulation that does *not* reproduce on hardware is still
  useful information — it bounds the model's fidelity. Record it as such rather
  than discarding it.
- Never claim a policy is safe. The harness finds failures; it cannot prove
  their absence, and any claim of coverage is a claim about the declared
  parameter space only.

## Regulatory framing

EU Machinery Regulation 2023/1230 applies from 20 January 2027, and machinery
with fully or partially self-evolving behaviour falls under Annex I Part A. The
delegated act defining adequate evidence is not due until 2028.

Consequences for how output is written: an assessor must be able to re-run any
cited result, read every predicate definition, and see what fraction of the
declared space was covered. Never state or imply that Faultline output
satisfies a notified body — no one can currently say what satisfies one.
