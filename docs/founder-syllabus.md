# What you have to know, as the person who built this

*3 October 2026. A syllabus for one job: being the technical founder of
Faultline specifically. Not for becoming a roboticist — `docs/learning-path.md`
is that, and it is the better document if that is what you want.*

Sources below are named by title and author rather than linked, because the
links in `docs/learning-path.md` were verified in August and these have not
been. Verify before trusting any of them.

---

## The standard you are being held to

You will not be examined. You will be **cross-examined**, by one engineer, in
one call, who has shipped robots for fifteen years and has already decided this
is probably nonsense.

The test is never "can you define domain randomisation." It is: you give an
answer, they ask the follow-up you did not expect, and the room finds out
whether you understand the thing or memorised a sentence about it.

That changes what you study. Reciting a method is worth nothing. Being able to
say *where it breaks, and what you did about that* is worth everything — and is
also, conveniently, the entire product.

**The bar: for every claim the harness makes, you can say what would have to be
true for it to be wrong.** If you cannot, you do not yet know that part.

---

## Part 1 — The eight questions, in the order they will come

This is the spine of the syllabus. Everything in Part 2 exists to answer one of
these.

### 1. "What are you actually perturbing?"

**Bad answer:** "physical conditions — friction, slope, that kind of thing."
They will hear vagueness and stop listening.

**What you must know:** all seven axes by name, unit and mechanism — what the
code *does* to the simulation for each one, which in `_apply_perturbation` is:

- `friction_mu` sets `geom_friction[:, 0]`, sliding friction only; torsional
  and rolling keep the model's values
- `slope_deg` rotates **gravity** rather than tilting the floor, so the contact
  geometry stays identical and the only thing varying between runs is the
  quantity under test
- `torque_loss_pct` scales `actuator_forcerange` and `actuator_gainprm[:, 0]`
  together — not a gear change
- `payload_kg` adds mass, shifts `body_ipos` toward the offset, and scales
  `body_inertia` by the mass ratio. **That last step is an approximation**, not
  the true parallel-axis result, and it is the first thing a careful engineer
  will catch. Know why it is defensible for a small payload and where it stops
  being
- `push_impulse_ns` becomes a force of `impulse / 0.05 s` applied through
  `xfrc_applied` over a 0.05 s window, spread that way to keep the solver stable

And which two things are *not* searchable — push time and yaw — and why they
belong on the base spec instead.

**Where it lives:** `harness/faultline/reduce.py` (`SEVERITY_AXES`),
`runner.py` (`_apply_perturbation`), skill `rigid-body-dynamics`.

**Prove it:** add an eighth axis end to end — registry, perturbation, reduction
target, test. If you cannot, you do not own the physics.

### 2. "Your simulator is wrong. Why do I care what it says?"

The single most important question in the business, and it will come in minute
three.

**Bad answer:** arguing that MuJoCo is accurate. It is not accurate enough, and
they know it better than you.

**What you must know:** that they are right; that fidelity is an arms race
nobody wins; that the answer is calibration rather than accuracy — pair a large
simulated campaign with a small number of matched hardware runs and produce a
statistically valid bound. That this is published method (SureSim,
arXiv:2510.04354) and that you have **not built it yet**. Say the last part.

You must also know the asymmetry that makes the current product honest anyway:
a failure found in simulation is a hypothesis, but a failure found *and
minimised* tells them exactly which condition to try on hardware. You are
selling them a cheap way to spend their expensive hardware time.

**Where it lives:** `docs/strategy.md` §3 Layer 2, skill
`uncertainty-and-evidence` (combining simulation with scarce hardware runs).

### 3. "You said 7.875 N·s. Did the robot get 7.875 N·s?"

**Bad answer:** yes.

**What you must know:** no. The impulse is spread over a 0.05 s window but
applied on a 0.02 s control grid, over-delivering by roughly 20% at the default
push time. Sensor lag rounds half-to-even onto the same grid, so delivered lag
is not monotonic in the requested value. This is why every number in every
document says **requested**.

This is your best question, not your worst. Volunteering a known defect that
the customer had not spotted is the fastest credibility you will ever buy, and
it is the thing a vendor who is bluffing cannot do.

**Where it lives:** `runner.py` (`steps_per_ctrl`, `lag_steps`), skill
`control-theory`.

**Prove it:** compute the delivered impulse for a requested value at three
different push times, by hand, then confirm it against the code.

### 4. "My policy takes a 48-element observation in this order. How does that work?"

This is not a trivia question — it is the actual integration work, and it is
where real engagements succeed or fail.

**What you must know:** that the observation is a **contract**, not a
convention; that a policy fed the same numbers in a different order does not
degrade gracefully, it behaves like a different policy; that joint order comes
from the model file and differs between a URDF export and a hand-written MJCF;
that gravity-in-body-frame and base angular velocity are in different frames
and it is easy to get one of them wrong in a way that looks almost right.

**Where it lives:** `harness/faultline/observe.py`, skills
`rl-for-robot-policies` (the observation is a contract) and
`spatial-maths-and-frames`.

**Prove it:** take a policy exported by someone else, map its observation, and
show the mapping is right by a test rather than by it not crashing.

### 5. "41%? There is no way our failure rate is 41%."

**Bad answer:** defending the number.

**What you must know:** they are right and the number is not a failure rate.
41.1% is the fraction of *directed* samples that violated a predicate, and a
directed search deliberately concentrates where violations are dense — so the
number describes the search, not the robot. Only the uniform-random samples
could support a rate, and five seeds of them cannot support one either.

**Where it lives:** skills `optimisation-and-search` (the statistical trap) and
`uncertainty-and-evidence` (directed search breaks the arithmetic).

This is a standing rule in `CLAUDE.md` for a reason: it is the single easiest
number on the site to misuse, and misusing it once in front of a customer
destroys the only thing you are selling.

### 6. "You found 51 failures. How many are there?"

**What you must know:** that you cannot answer, and why. That finding failures
is strong evidence and finding none is weak evidence. The rule of three — with
*n* runs and zero failures, the upper 95% bound on the rate is about 3/*n*, so
300 clean runs buys you "below 1%" and nothing better. That a search which
found nothing may have been looking in the wrong place, and your coverage
figure (87 of 4096 cells, 2.1%) says exactly how much of the volume it even
visited.

**Where it lives:** skill `uncertainty-and-evidence` (binomial basics, the
claims ladder), `harness/faultline/report.py` (`measure_coverage`).

**Prove it:** compute, by hand, how many clean runs the published campaign
would need to support a claim of "under 0.5%, 95% confidence". Then notice that
the campaign cannot support it at all, because the samples were not uniform.

### 7. "Can you reproduce it? Can I?"

**What you must know:** three separate seeds — sampler, sim, policy — and why
one global seed hides which component caused a divergence. The exact MuJoCo pin
(3.12.0) and why it is pinned exactly rather than loosely: contact solvers
change between minor versions, and a campaign that cannot be re-run on the same
physics is not evidence. What the archive contains and what `faultline replay`
checks.

**Where it lives:** `harness/faultline/record.py` (`replay`), `harness/pyproject.toml`,
skill `robot-policy-testing` (reproducibility is the product).

**Prove it:** break reproducibility deliberately — change one seed, or unpin
MuJoCo — and watch exactly which part of the record catches it.

### 8. "Would a notified body accept this?"

**The only correct answer:** nobody can currently say, because the delegated
act defining adequate evidence is not due until 2028, while the regulation
applies from 20 January 2027.

**What you must know:** that this gap is the opportunity and also the risk;
that your job is to produce evidence that is *re-runnable and auditable*, which
is the one property every plausible version of the standard will require; and
that the moment you say "compliant" you have taken on liability you cannot
carry.

**Where it lives:** `docs/founder-brief.md` §5, skill `robot-policy-testing`
(regulatory framing).

---

## Part 2 — The five bodies, in dependency order

Each one says why it is load-bearing *for this company*. Skip the "why" at your
peril; it is the difference between studying and collecting.

### A. Rigid-body dynamics and frames

**Why:** it is the substrate under every number you produce. A frame error does
not crash — it produces a plausible wrong answer, and you ship it.

Know: generalised coordinates, and why a free joint is 7 `qpos` and 6 `qvel`;
joint and DOF addressing; mass, inertia and the parallel-axis effect of an
offset payload; contact as a constraint problem and what the solver parameters
mean; why `qvel[0:3]` is world-frame linear and `qvel[3:6]` is body-frame
angular; rotation matrices, why the transpose is the inverse, quaternion
ordering traps; where `arccos` loses precision near zero tilt; the four
divergence classes.

**Read:** skills `rigid-body-dynamics` and `spatial-maths-and-frames`, then
`harness/faultline/model.py` and `runner.py`. Externally: the MuJoCo
documentation's computation chapter, and *Modern Robotics* (Lynch & Park) for
screws and frames. *Rigid Body Dynamics Algorithms* (Featherstone) if you want
the real thing.

**Roughly:** 4–6 weeks at a real pace.

### B. Control theory

**Why:** both known defects in the harness live here, and this is the subject a
customer's controls engineer will test you on first.

Know: the two clocks — physics timestep against control rate — and zero-order
hold between them; actuator models, gear, torque limits and saturation; what
sensor latency does to a closed loop; and quantisation, which is the general
case of both your bugs: a continuous requested value applied on a discrete grid
is not the value you requested.

**Read:** skill `control-theory`, then `runner.py`. Externally: *Feedback
Systems* (Åström & Murray) — the free PDF is the standard reference.

**Roughly:** 4 weeks. Highest return per hour of anything on this list.

### C. Statistics and evidence

**Why:** this is the moat. `docs/strategy.md` names Layer 2 as the defensible
part, and the reason it is defensible is that no robotics team wants to staff
it. If you are not the person who understands it, the company has no second
layer.

Know: binomial confidence intervals and the rule of three; why directed
sampling invalidates rate arithmetic; coverage against confidence, and why they
are not the same axis; what a minimal case is and is not; prediction-powered
inference well enough to implement it, not just cite it.

**Read:** skill `uncertainty-and-evidence`, then SureSim (arXiv:2510.04354) —
properly, with the maths, not the abstract. Externally: any solid intro to
statistical inference; Hanley & Lippman-Hand's 1983 note is the original source
for the rule of three and is two pages.

**Roughly:** 6–8 weeks, and the least optional thing here.

### D. Search and optimisation

**Why:** it is the wedge, and it is also the part a competent ML engineer
rebuilds in a fortnight — so understanding *why* it works is worth more than
having it.

Know: severity as a signed margin, and why binary pass/fail cannot be
optimised; the Cross-Entropy Method (not Covariance Matrix Adaptation — they
are different things and confusing them in a call is fatal); elite fraction
(0.25 here); variance collapse and the floor that prevents it; why parallel
execution must not change a result.

**Read:** skill `optimisation-and-search`, then `harness/faultline/search.py`
and `reduce.py`.

**Roughly:** 2–3 weeks. You already have most of this.

### E. Reinforcement learning

**Why:** you do not need it to test a policy — the harness treats the policy as
frozen and opaque, which is the premise. You need it to speak the customer's
language, to map their observation contract, and to not be visibly ignorant
about how the thing you are testing came to exist.

Know: MDPs, policy and value, PPO at the level of what its hyperparameters do;
observation and action spaces as a contract; reward shaping and why it produces
the weird failure modes you will find; domain randomisation against test-time
perturbation, and why they are *not* the same operation; distribution shift;
and why code coverage means nothing for a network.

**Read:** skill `rl-for-robot-policies`, then `observe.py` and `adapters.py`.
Externally: Sutton & Barto for the foundations; the PPO paper; one of the
standard implementations read end to end.

**Roughly:** 6 weeks. Deliberately last.

---

## Part 3 — What to skip, and why

You will be tempted by all of these. Each costs months.

| Skip | Why |
| --- | --- |
| **Training policies yourself** | The harness treats the policy as frozen. Useful eventually, never on the critical path. You need enough to *read* a training setup, not to run one. |
| **Writing a simulator** | `docs/strategy.md` calls this the most important structural decision in the company: do not fight NVIDIA and MuJoCo. Own the layer above. |
| **Perception, vision, SLAM** | You test control policies. The observation arrives as a vector. Perception is a different company. |
| **ROS 2 internals** | Integration surface, not knowledge. Learn it the week a customer needs it. |
| **Electronics and firmware** | Furthest from the business, most fun, which is exactly the trap. `docs/learning-path.md` Gate 1 is a legitimate hobby and not this job. |
| **Deep learning theory** | Backprop, attention, transformers. None of it touches a frozen policy's forward pass. |

---

## Part 4 — The non-technical knowledge that is still *yours*

You asked about the tech. These four sit beside it and nobody else will learn
them for you.

**The regulation, first-hand.** Read Regulation (EU) 2023/1230 — at minimum
Annex I Part A and the definitions — rather than summaries of it. You will be
in rooms with people who have read it, and secondhand knowledge is audible. Know
what a notified body is, what conformity assessment means procedurally, and the
distinction between a harmonised standard and a delegated act.

**How a robotics team is actually organised.** Who owns the policy, who owns
the controls stack, who owns safety, who signs a purchase order, and which of
them you are talking to. You will mostly reach ML engineers, who are not the
budget holder, and whose instinct is to build it in-house.

**Reading a paper properly.** You will be competing with people who read SureSim
and decided not to productise it. The skill is reading the method section well
enough to implement, and the limitations section well enough to know what it
does not claim.

**Technical writing under the standing rules.** The engineering report and
safety appendix are the product. Writing one sentence that overstates is the
whole risk of this business in a single line of text. `CLAUDE.md` is the
compressed version of what you may say.

---

## Part 5 — Exercises that prove it

Not quizzes. Each produces something that stays in the repo.

1. **Add the eighth axis.** Registry, perturbation, reduction, test. Proves A.
2. **Fix the impulse over-delivery** so the delivered impulse matches the
   requested one on the control grid, and write the test that would have caught
   it. Proves B, and removes a real defect.
3. **Fix sensor-lag monotonicity**, or prove it cannot be fixed without
   changing the control rate, and document which. Proves B.
4. **Write the confidence-interval calculator** — given runs and failures,
   produce the interval and the claim it licenses, and refuse where the sample
   was directed. Proves C, and is the first brick of Layer 2.
5. **Implement `faultline diff`** — roadmap A5, the Layer 1 product surface
   that does not exist yet. Proves D, and is the most commercially valuable
   item on this list.
6. **Map a stranger's policy.** Take any public quadruped checkpoint, map its
   observation, run a campaign. Proves E, and is the first time the harness
   touches something you did not write.
7. **Write the one-page answer to "your simulator is wrong"** and show it to
   someone who will argue. Proves you can hold question 2 under pressure.

Items 2, 3 and 5 are the ones that also move the company.

---

## Part 6 — Sequence

Roughly six months if this is a serious second job, longer if it is not. The
order matters more than the pace.

| | What | Why then |
| --- | --- | --- |
| 1 | Control theory (B) | Your known bugs; the first thing you get asked |
| 2 | Rigid-body dynamics and frames (A) | The substrate under every number |
| 3 | Statistics and evidence (C) | The moat; start before you need it |
| 4 | Search and optimisation (D) | Mostly consolidation of what you have |
| 5 | RL (E) | The customer's language, not your bottleneck |

Run Part 1 in parallel from day one. You will be asked those eight questions
long before this list is finished, and "I don't know yet, here is what I do
know" is an acceptable answer exactly once per question.

---

## The one thing to remember

Everything here serves a single sentence you must be able to say truthfully, in
a room, without hedging:

> *This is what we found, this is the condition that causes it, here is the
> archive that lets you check us, and here is precisely what it does not prove.*

The last clause is the one that takes six months to earn.
