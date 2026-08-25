# Faultline: the whole problem, from scratch

You are building a company in a field you did not train in. This file exists so
you can hold a conversation with a robotics engineer, follow what they say,
push back when they are wrong, and know which questions are the hard ones.

No robotics or machine-learning background assumed. Nothing here is simplified
to the point of being useless — where something is genuinely difficult, it says
so rather than pretending otherwise.

Read it once top to bottom. After that it is a reference.

The other documents in this repo assume you already know this material:
[strategy.md](strategy.md) argues the business case, [product-spec.md](product-spec.md)
specifies the product, [roadmap.md](roadmap.md) sequences the build. This one
explains the world all three sit in.

---

## Contents

1. [The world this lives in](#1-the-world-this-lives-in)
2. [Why learned policies fail](#2-why-learned-policies-fail)
3. [Glossary](#3-glossary)
4. [What Faultline actually does](#4-what-faultline-actually-does)
5. [The regulation](#5-the-regulation)
6. [The academic field you are standing in](#6-the-academic-field-you-are-standing-in)
7. [What to read, in order](#7-what-to-read-in-order)
8. [Questions you should be able to answer](#8-questions-you-should-be-able-to-answer)

---

## 1. The world this lives in

### What a robot policy is

A robot has motors and sensors. Something has to decide, many times per second,
what each motor should do based on what the sensors say. That something is the
**controller**.

For most of robotics history controllers were written by hand: equations
derived from physics, tuned by an engineer who could explain every term. This
still works well for a robot arm bolted to a factory floor doing the same
motion a million times.

It works badly for a robot that walks over ground it has never seen. Nobody can
write the equations for "stay upright on wet moss with a 3 kg parcel strapped
slightly off-centre." So instead the controller is **learned**: a neural network
is trained, usually in simulation, by trying an enormous number of times and
being rewarded when it does well.

That learned controller is a **policy**. In our harness it is anything with two
methods:

```python
policy.reset(seed)          # start a fresh episode
policy.act(observation, t)  # given what the sensors say, return motor commands
```

It runs at some fixed rate — our default is 50 Hz, so fifty decisions a second.
Between decisions the physics advances in much smaller steps (our quadruped
model uses a 0.002 s timestep, so 500 physics steps a second).

### Why this breaks every testing instinct from software

This is the single most important idea in the document. If you take away one
thing, take this.

Ordinary software is made of branches. `if user is logged in`, `else`. You can
count the branches, write a test for each, and measure **code coverage**: the
percentage of lines or branches your tests reached. Hit 100% and you have at
least executed every path the author wrote. It is not proof of correctness, but
it is a real, meaningful number.

A neural network has no branches. It is a pile of multiplications. There are no
lines to cover, no paths to enumerate, no `else` you forgot. Every input
produces an output, always, and nothing about the code tells you which inputs
are dangerous.

**So coverage — the central idea of software testing — means nothing here.**
You cannot ask "did we test all of it?" because there is no "all of it" to
enumerate. The question has to change entirely: not *did we cover the code*,
but *did we cover the situations*.

And situations are continuous. Slope is not a branch, it is a number between 0
and 25 degrees, with infinitely many values in between. So is friction, so is
sensor delay, so is payload mass. The space of situations is not a list you can
tick off. It is a volume.

That reframing is what the whole company rests on. Faultline does not test
code. It searches a volume.

### Two ways of thinking about the same robot

You will hear engineers move between these without signalling, and it is
confusing until you notice:

- **The robot as hardware** — motors, gearboxes, an IMU, a battery. Physical,
  expensive, breakable.
- **The robot as a model** — a file describing the same machine as bodies,
  joints, masses and inertias, which a simulator can compute with.

Faultline works entirely on the second. That is a strength (fast, cheap,
repeatable, nothing breaks) and it is the source of the field's hardest
problem, which is §2.

---

## 2. Why learned policies fail

### 2.1 Distribution shift — the big one

A policy is trained on some distribution of conditions. Perhaps the training
simulator randomised friction between 0.6 and 1.0, slope between 0 and 10
degrees, and never simulated sensor delay at all.

Deploy it where friction is 0.4, or the slope is 14 degrees, or the depth camera
answers 60 ms late under load, and the policy is being asked about a situation
it has no experience of. It does not know that. It has no mechanism for saying
"I have not seen this." It confidently outputs motor commands, and those
commands are whatever the network's shape happens to produce out there.

This is **distribution shift**, and it is the dominant cause of learned-policy
failure. Note what it is *not*: it is not a bug in the sense of a mistake in the
code. The network is working exactly as built. It was simply never shown this.

The failures are rarely exotic. They are ordinary conditions that were never
sampled — which is precisely why nobody wrote a test for them.

### 2.2 The sim-to-real gap

Since training and testing both happen in simulation, everything depends on how
close the simulation is to reality. It is never exactly close. The difference is
the **sim-to-real gap**, and it is the field's central difficulty.

The error sources, in roughly the order they hurt:

**Contact and friction, by a wide margin.** What happens when a foot touches
the ground is genuinely hard physics — deformation, micro-slip, materials that
behave differently when wet, cold or worn. Simulators approximate this with a
contact model and a friction coefficient. Real contact is not one number.

**Actuator dynamics, second.** A simulated motor is often treated as producing
whatever torque is asked. A real motor has a torque-speed curve, gearbox
friction, thermal limits that reduce output as it heats, and a control loop of
its own that takes time to respond.

**Sensing and latency, third.** Simulated sensors are typically perfect and
instant. Real ones are noisy, drift with temperature, and arrive late — and how
late varies with system load.

The honest consequence, which our own documentation states and which you should
never soften: **a failure found in simulation is a hypothesis about the hardware
until the hardware reproduces it.** Faultline finds conditions where a policy
fails *in simulation*. Whether that predicts reality is a separate claim
requiring separate evidence, and it is the reason calibration is Phase C of the
roadmap rather than a nice-to-have.

There is a useful flip side: a simulated failure that does *not* reproduce on
hardware is still information. It bounds how wrong the model is, and that is
worth recording rather than discarding.

### 2.3 Why "we tested it" is not evidence

A robotics team will tell you they tested the policy. They mean they ran it on
a suite of scenarios — walk over the gravel patch, climb the ramp, get shoved.

Passing a hundred scenarios tells you about a hundred scenarios. It says nothing
about the hundred and first, and there is no coverage number to tell you how
much of the space those hundred represent — because, per §1, there is no
meaningful coverage number for a network.

Worse, the scenarios are chosen by the same people who trained the policy, out
of the same intuitions about what matters. The conditions nobody thought of are
exactly the conditions nobody wrote a scenario for.

### 2.4 Why failures cluster

Failures are not scattered points. They occupy **regions**.

If a robot topples under an 11 N·s shove, it almost certainly topples under 12,
and 13. The failing conditions form a connected region of the space, not a
sprinkle of unlucky individual cases.

Two consequences shape our whole product:

1. **Counting failures is close to meaningless.** Run a bigger budget, sample
   more densely inside the same region, get a bigger number — describing exactly
   the same problem. A count moves with the budget and invites an argument
   instead of a decision.
2. **Failures should be reported as modes, not counts.** "It falls under a push
   alone" and "it falls only when a push combines with weak actuators" are two
   different engineering problems with two different fixes. That distinction is
   what a customer can act on.

This is why Faultline's output is a handful of named modes rather than a tally.

---

## 3. Glossary

### Robots and simulation

**Degrees of freedom (DOF)** — how many independent ways the robot can move. A
robot arm with three rotating joints has three. Our stand-in quadruped has
twelve: three joints per leg.

**Joint** — a connection allowing relative motion between two rigid parts.
*Hinge* joints rotate about one axis (a knee). *Slide* joints move along one
axis. *Ball* joints rotate about three (a shoulder). *Free* joints have all six
— three of position, three of rotation — and are used for a body floating in
space rather than attached to anything.

**Floating base vs fixed base** — a legged robot's body floats: it can move and
rotate freely, so its position is part of the state, and it can fall over. An
arm bolted to a bench has a fixed base: it cannot fall, and different things
count as failure. This distinction caused a real bug in our code, described in
§4.6.

**Actuator** — the thing that drives a joint. A motor. A model can describe a
joint with no actuator, in which case the joint moves passively but no policy
can command it.

**URDF** (Unified Robot Description Format) — an XML file describing a robot as
links and joints, from the ROS ecosystem. Widely used, and **it carries no
contact parameters and no actuator dynamics worth trusting**. A URDF converted
straight to a simulator usually has no actuators at all, which is why our loader
refuses such a file with an explicit message.

**MJCF** — MuJoCo's own XML format. Richer than URDF: contact parameters,
actuator models, solver settings, and named poses.

**MuJoCo** — the physics simulator we use. Originally from a research lab,
bought by DeepMind, now open source. Fast and well regarded for contact-rich
simulation. What "Multi-Joint dynamics with Contact" stands for tells you what
it is for.

**CAD** (STEP, SolidWorks files) — how the mechanical engineer designed the
parts. **CAD cannot be simulated directly.** It describes shape; it does not
describe joint axes, masses or inertia tensors. Getting from CAD to URDF is a
separate manual export step, which is why our config builder refuses CAD with
an explanation rather than accepting it.

**Timestep** — how far the simulator advances per physics step. Ours is 0.002 s.
Smaller is more accurate and slower. Too large and the simulation becomes
numerically unstable.

**Solver** — the algorithm computing forces at each step, particularly contact
forces. Ours is pinned to Newton with fixed iterations, because a result that
cannot be re-run on the same solver settings is not evidence.

**Keyframe** — a named pose stored in the model, e.g. "standing". Without one
there is no defined starting posture, which our loader warns about because it
changes what a run means.

**Divergence** — the simulation becoming numerically unstable and producing
infinities or NaNs. Physically meaningless. §4.6 explains why this mattered
enormously to us.

### Learning

**Policy** — the learned controller. See §1.

**Checkpoint** — a saved copy of the network's weights at a moment in training.
Teams produce many. Which one is deployed matters enormously, which is why we
identify a policy by the hash of its file contents rather than its path — paths
get overwritten and then a run history is a lie about which network produced
which result.

**Observation** — what the policy is given each step. Not the raw world: a
specific vector, in a specific order, in specific units. Typically things like
body orientation, joint positions, joint velocities, and the previous action.

**Action** — what the policy returns. Usually a target position or torque per
actuator.

**Reinforcement learning (RL)** — training by trial, error and reward, rather
than from labelled examples. The robot tries, gets a score, adjusts.

**PPO (Proximal Policy Optimization)** — the RL algorithm most locomotion
policies are trained with. You do not need to know how it works, only that when
someone says "our PPO policy" they mean a network trained this way.

**Domain randomisation** — deliberately varying simulator parameters during
training (friction, masses, delays) so the policy sees a range instead of one
fixed world. The standard defence against the sim-to-real gap, and a partial
one: it broadens the training distribution but does not tell you where the
broadened distribution ends.

**ONNX** — an open format for a trained network, exportable from most
frameworks and runnable without them. Our preferred way to accept a customer's
policy: they export, we run it, no shared Python environment needed.

**TorchScript** — PyTorch's own portable format. Same idea.

**Distribution shift** — see §2.1.

### Testing

**Perturbation** — a specific change to the world for one run: a shove of this
size, a slope of this angle, a sensor this late. Our harness varies seven, each
in physical units:

| Field | Unit | Plain meaning |
| --- | --- | --- |
| `push_impulse_ns` | N·s | a shove to the body |
| `slope_deg` | deg | how steep the ground is |
| `sensor_lag_ms` | ms | how late the policy sees the world |
| `torque_loss_pct` | % | strength lost in the motors |
| `payload_kg` | kg | extra mass carried |
| `payload_offset_m` | m | how far off-centre that mass sits |
| `friction_mu` | – | floor friction |

Note the units. Nothing is normalised to 0–1 — an engineer reading a report
needs to see `slope_deg = 18`, not `slope = 0.72`.

**Newton-second (N·s)** — the unit of impulse: force multiplied by the time it
is applied. A short hard shove and a long gentle push can carry the same
impulse. It is the honest way to describe "a shove" because it does not depend
on how long you shoved for.

**Predicate** — an explicit rule defining failure. `tilt_deg > 35` — if the body
tilts more than 35 degrees, that run failed. Written by the customer, checked
over the whole trajectory, and deliberately **never a learned classifier**: the
moment a black box decides what counts as failure, the evidence stops being
checkable by anyone.

Our harness computes exactly four signals a predicate may read: `tilt_deg`,
`height_m`, `contact_force_n`, `joint_vel_rads`.

**Grace period** — time at the start of a run during which violations are
ignored, so a settling transient is not reported as a failure.

**Severity** — how badly a rule was broken, as a signed number. Negative means
passing with margin, positive means violated. It gives the search a gradient to
follow: "this run was closer to failing than that one" is information a pure
pass/fail cannot express.

**Seed** — the number initialising a random generator. Same seed, same sequence,
same result. Seeds are what make a random process repeatable.

**Determinism** — the same inputs producing exactly the same outputs, every
time. The foundation of the entire product: if a run cannot be repeated, it is
an anecdote rather than evidence. We keep **three separate seeds** — sampler,
simulator, policy — so that when two runs differ we can tell which component
caused it. One seed would hide that.

**Falsification** — searching for a case that breaks a stated property, rather
than trying to prove none exists. The academic name for what Faultline does.
See §6.

**Minimisation / reduction** — taking a failing case with many things wrong at
once and stripping away everything that did not matter, leaving the smallest
condition that still fails.

**Coverage** — here, what fraction of the *declared parameter space* was
actually sampled. Not code coverage. Ours is deliberately blunt: with six axes
and four bins each there are 4,096 cells, and a few hundred samples cannot fill
them. Stating that plainly is the point.

### Ours

**Campaign** — one search over one declared space, against one policy: a budget
of simulations, a method, a seed.

**Failure mode** — a group of failures that need the same axes after reduction.
The signature is `(predicate, required_axes)`. "Falls under a push alone" is one
mode; "falls only under a push plus weak actuators" is a different one.

**Region** — the box in parameter space a mode occupies, per required axis
(min, median, max). How the diff detects a mode getting *wider*.

**The three deliverables** — the engineering report (failure modes and their
minimal cases), the safety-case appendix (method, every predicate, coverage,
and the limits of the evidence, written for an assessor), and the run archive
(seeds, hashes and verdict for every run, so anyone can re-run any of it).

---

## 4. What Faultline actually does

Five stages. Everything below is measured from this repo, not asserted.

### 4.1 Ingest

Load the robot model and the policy, and record enough to make any result
re-runnable: the file hashes, the seeds, the simulator version.

The harness resolves from the model what it used to assume — which body is the
base, whether it floats, which joint indices are actuated. It refuses, naming
the problem, a model with no actuators, no drivable joints, or a base name that
does not exist.

Policies load from an exported file (`policy: onnx:walk-v41.onnx`), and three
things are checked before a campaign starts rather than discovered during one:
identity is the file's content hash; the network must be deterministic (the same
observation twice must give the same action, which catches dropout left enabled
at export); and action widths must match the model's actuator count.

### 4.2 Perturb

Each run is one point in the declared space — a specific friction, slope,
latency, payload and shove, applied together. Combinations matter: the
interesting failures are almost never on one axis alone.

### 4.3 Search — and why directed beats random

Random sampling covers the volume evenly. **Directed search** (we use the
cross-entropy method, CEM) fits a distribution to the most severe results so
far and resamples from it, concentrating budget where violations are dense.

Measured on our published campaign, five seeds by 150 simulations each:

| Method | Hit rate |
| --- | --- |
| Random | 3.9% |
| Directed (CEM) | 41.1% |

An order of magnitude more failures for the same compute.

One honest caveat we publish: directed search is **not** faster at finding the
*first* failure, because CEM's opening round is uniform — identical to random by
construction. Its advantage is everything after that.

A note on terminology, since it matters if you talk to a researcher: CEM is an
adaptive sampler. It is **not a trained adversary** — there is no learning, no
gradients, no training run. The landing page used to claim otherwise and it was
corrected.

### 4.4 Detect

Every trajectory is checked against the customer's predicates, over the whole
run rather than just the final state. A run is flagged only when a rule *they
wrote* evaluates true.

### 4.5 Reduce

A raw failing run perturbs several axes at once and is a poor bug report — the
customer cannot tell which mattered. Reduction relaxes each axis back toward
nominal for as long as the failure survives.

A real example from this repo: a search found failures from 9.68 N·s upward, and
reduction proved the policy topples at **7.96 N·s** with everything else at
nominal — below anything the search had sampled. The gap between "where we found
failures" and "the smallest condition that actually fails" is the difference
between a test suite and an adversary.

The result is described as **locally minimal**: relaxing any listed axis further
stops the failure, but a different combination might still be smaller. We say
that explicitly rather than implying we found the global minimum.

### 4.6 The bug that taught us the most

Worth understanding in full, because it shows what "trustworthy evidence"
actually demands.

Running the harness on a robot arm for the first time, a badly tuned test policy
made the simulation numerically diverge — MuJoCo warned forty times that the
simulation was unstable. **The harness recorded every one of those as a policy
failure.** After reduction they read as "fails under no perturbation at all,"
which is exactly what a diverged run looks like once minimised.

A blown-up solver is not evidence of a fault in the robot. Reporting it as one
is the worst mistake this product could make: it invents a defect the machine
does not have.

Chasing that turned up something worse. Past roughly 1e12, MuJoCo stops
diverging — it flags the control as bad, **silently resets it to zero**, and the
run finishes numerically perfect. A policy emitting garbage would have been
recorded as *passing every predicate*.

Both are closed now. Four things mark a run **invalid** — never counted as a
failure, excluded from the search fit so instability is not mistaken for a
promising region:

1. the solver diverged
2. MuJoCo rejected the control (the silent-zero case)
3. the policy returned a non-finite action
4. the action was the wrong width

The general lesson: for a product selling evidence, **the dangerous failures are
the ones that look like valid results.**

### 4.7 Report

Failures are grouped into modes, coverage is stated conservatively, and three
deliverables are written. The safety appendix never claims a policy is safe —
there is a test in the suite that fails if affirmative safety language appears
in generated text. It finds failures; it cannot show their absence.

---

## 5. The regulation

### What is changing

**EU Machinery Regulation 2023/1230** replaces the old Machinery Directive on
**20 January 2027**. Being a Regulation rather than a Directive, it applies
directly and identically in every member state — no national transposition, no
local variation.

### The part that matters to us

Its Annex I lists categories needing **third-party conformity assessment**, and
one of them covers safety components with fully or partially self-evolving
behaviour using machine-learning approaches.

Unpacking that:

**Conformity assessment** — proving a product meets the rules before it can be
sold in the EU. For most machinery the manufacturer does this themselves:
self-certification.

**Third-party / notified body** — an independent organisation, designated by a
member state, that assesses on the regulator's behalf. Slower, expensive, and
not optional for the categories that require it.

**Safety component** — a part whose failure endangers people. A learned policy
that keeps a robot from falling on someone is squarely one.

**Self-evolving behaviour** — behaviour that changes, whether continuously
learning in the field or updated by retraining.

Put together: **a learned policy performing a safety function cannot be
self-certified.** A notified body must sign it.

### The part nobody knows

The delegated act defining what counts as *adequate evidence* is not due until
2028.

So assessment becomes mandatory roughly a year before anyone agrees what passing
looks like. Notified bodies have no settled methodology for learned control —
there is no established answer to "what would convince you this policy is safe?"

That is the opportunity and the risk in one sentence. Whoever supplies the
evidence format they converge on is positioned extremely well. Nobody can
currently promise that any particular output satisfies a notified body, and
**we must never imply otherwise** — it is written into our own conventions as a
rule.

---

## 6. The academic field you are standing in

This is not a new idea. It has a literature and a name, and knowing it is worth
a lot in a conversation with a researcher.

The field is **falsification of cyber-physical systems**. A cyber-physical
system is software controlling physical things — a car, an aircraft, a robot.
Falsification means searching for an input that violates a stated property,
rather than trying to prove no such input exists.

Its vocabulary maps almost directly onto ours:

| Their term | Ours |
| --- | --- |
| Specification / temporal logic property | Predicate |
| Robustness (how far from violating) | Severity |
| Falsification loop | Directed search |
| Counterexample | Failing run |
| Counterexample minimisation | Reduction |

**Signal temporal logic (STL)** is the usual language for writing those
properties — it can express things ours cannot, like "within 2 seconds of the
push, the body must return upright." Its **robustness semantics** give a signed
number for how well a property held, which is exactly the role severity plays
for us. If we ever need richer rules than a threshold on a signal, this is where
to look.

Two things follow from this:

1. **The method is respectable.** You are not selling a gimmick; you are
   productising an established research approach for a domain that has not had
   it applied properly.
2. **The differentiation is not the algorithm.** CEM is textbook. What is not
   commodity is the evidence chain, the calibration to reality, and the
   integration into a team's daily workflow — which is exactly the argument
   [strategy.md](strategy.md) makes.

---

## 7. What to read, in order

**A caveat you should hold onto:** web search hit its session limit while this
was written, so the links below come from my own knowledge rather than fresh
lookups. The works are real and well known, but a URL may have moved. Search
terms are given so you can find each regardless. Where I am not certain
something exists in a particular form, it says so rather than guessing.

### Start here — the robots

1. **MuJoCo documentation** — <https://mujoco.readthedocs.io>. Read the
   overview and the "Computation" page. You do not need the maths; you need to
   see what a simulator actually decides and where approximations enter. The
   best hour you can spend.
2. **The MJCF modelling guide**, same site. Read one model file alongside it —
   ours is `harness/models/quadruped.xml`, deliberately small and commented.
3. **URDF documentation** — the ROS wiki (search "ROS URDF tutorial"). Skim
   only. The point is to see how little a URDF says about contact and actuators.

### Then — the learning

4. **Spinning Up in Deep RL** (OpenAI) — <https://spinningup.openai.com>. The
   clearest introduction to reinforcement learning that exists. Read "Part 1:
   Key Concepts". Stop before the algorithm derivations unless you want them.
5. **Domain randomisation** — search for *"Domain Randomization for Transferring
   Deep Neural Networks from Simulation to the Real World"* (Tobin et al.,
   2017). The origin of the standard defence against the sim-to-real gap. Read
   the abstract and introduction.
6. **Learning agile and dynamic motor skills for legged robots** (Hwangbo et
   al., *Science Robotics*, 2019). The landmark sim-to-real locomotion result.
   Read it for how carefully they treat the actuator model — it is the paper
   that made actuator dynamics a first-class concern.

### Then — the testing

7. **SureSim** — *Reliable and Scalable Robot Policy Evaluation with Imperfect
   Simulators*, <https://arxiv.org/abs/2510.04354>. Read this one properly. It
   is the statistical method behind Phase C of our roadmap: combining a large
   simulated campaign with a few real-world runs to produce a *valid confidence
   interval* on real performance. The answer to "your simulator is wrong."
8. **Falsification of cyber-physical systems** — search for a survey, and for
   the tools **S-TaLiRo** and **Breach**, which are the long-standing academic
   falsification toolchains. Reading their documentation will show you the
   vocabulary of §6 in use.
9. **Signal temporal logic robustness** — search "STL robustness semantics".
   Worth understanding conceptually even if we never adopt STL.

### Then — the regulation

10. **Regulation (EU) 2023/1230** itself, on EUR-Lex. Read the recitals for
    intent, then Annex I. Long and legalistic; read the parts about
    self-evolving behaviour and skip the rest.
11. **A notified-body explainer** — search "notified body conformity assessment
    machinery regulation". Any reputable certification body's guide will do;
    they publish these to attract clients.

### Watch the competition

12. **Foretellix** and **Applied Intuition** — read their product pages
    carefully. This approach is mature in automotive; they are the closest thing
    to prior art for how it gets sold, packaged and priced.

---

## 8. Questions you should be able to answer

If you can answer these without looking, you can hold the conversation.

**On the problem**
1. Why does code coverage mean nothing for a neural network?
2. What is distribution shift, and why is it not a bug in the ordinary sense?
3. What are the three largest sources of sim-to-real error, in order?
4. Why is counting failures close to meaningless?

**On the domain**
5. What is the difference between a URDF and an MJCF, and why does it matter?
6. Why can CAD not be simulated directly?
7. What is an impulse measured in N·s, and why use it instead of force?
8. Why do we keep three separate seeds instead of one?

**On our product**
9. What is a failure mode, and what exactly makes two failures the same mode?
10. Why is reduction more valuable than the raw failing case?
11. Give the two hit rates for random versus directed search, and name the one
    thing directed search is *not* better at.
12. Name the four ways a run can be invalid, and why the silent one is the worst.

**On the business**
13. What changes on 20 January 2027, and what will still be unknown then?
14. Why can a learned safety function not be self-certified?
15. What is the one artifact worth more than everything else we could build?

*(15 is in [strategy.md](strategy.md): a failure mode found in a real
customer's policy, that they did not know about, which they then reproduced on
hardware.)*

---

## Where to go from here

- The business argument: [strategy.md](strategy.md)
- What the product should become: [product-spec.md](product-spec.md)
- What gets built, in order: [roadmap.md](roadmap.md)
- How the harness works, technically: [../harness/README.md](../harness/README.md)
- Run it yourself: the install and first run are the first ten lines of
  [../harness/README.md](../harness/README.md), or use the builder at `/configure/`

The fastest way to make this concrete is to run a campaign and read the report
it produces. Fifteen lines of config, about a minute, and every abstraction
above becomes a number you can look at.
