# Faultline — strategy

*Written August 2026. Every market claim links to a source. Every number that
is an estimate says so.*

---

## The one-sentence version

Robot companies are shipping learned policies they cannot evaluate, into a
market where, from January 2027, a third party must sign off on exactly that
kind of software. Faultline finds where a policy breaks, proves the finding is
reproducible, and produces the evidence.

---

## 1. What we actually have today

Honesty first, because the rest of this document is worthless if this section
is inflated.

The harness is 3,514 lines of tested Python (110 tests). It runs a MuJoCo
simulation of a quadruped, perturbs ten physical axes, checks explicit
violation predicates, searches the space with CEM, reduces any failure to a
minimal reproducing case, and emits an engineering report, a safety appendix
and a re-runnable archive. Every run is reproducible from three seeds, and the
recorded environment lets a divergence be attributed rather than argued about.

What it is not: it runs **our** robot model, **our** stand-in policies, at
**our** scale — 150 simulations on one machine. No robotics team would call
that evaluation. Nobody outside this repo can point it at their own robot and
get an answer.

That gap is the entire subject of this document.

---

## 2. The strategic reframe

Faultline currently *searches for failures*. That is a feature, and a copyable
one — CEM is a textbook method, and a competent ML engineer rebuilds it in a
fortnight. Search is not a company.

**The product is a verdict with a confidence interval, backed by a
reproducible evidence chain.**

Compare:

> "We ran 50,000 conditions and found 3 failure modes."

> "Your policy's real-world failure rate is below 0.4% with 95% confidence.
> Here are the three conditions where it breaks, each with a minimal repro, and
> here is the archive anyone can re-run to check us."

The first is interesting. The second is a purchase, and it is the only one of
the two that a notified body can use. Everything below is organised around
being able to say the second sentence truthfully.

---

## 3. The product — three layers

### Layer 1 — The gate

**Policy CI.** A team pushes a checkpoint; Faultline runs an adversarial
campaign and answers one question: *what got worse?*

```
checkpoint v41 vs v40
  ✗ 2 new failure modes
      tilt_limit  via push_impulse ≥ 6.2 N·s          [minimal repro attached]
      foot_slip   via friction ≤ 0.31 + slope ≥ 8°    [new — absent in v40]
  ✓ 1 mode fixed  (payload + torque_loss)
  → 4 modes total, 2 regressions.  BLOCKING
```

This is a *daily* pain, not a 2027 pain. Teams retrain constantly — new data,
new reward shaping, new domain randomisation. Today they evaluate on a fixed
episode set, plus scarce hardware time, plus intuition. There is no CI. A
checkpoint that is worse in one specific corner of the state space is caught on
hardware, or not at all.

Layer 1 sells with no reference to regulation. It is the layer that generates
usage, and usage generates the data the other two layers need.

### Layer 2 — The estimate

Layer 1 has one fatal objection, and a good engineer raises it in minute three:

> *"So what? Your simulator is wrong."*

They are right. A failure found in an imperfect simulator may not exist on the
robot, and a policy that passes may still fall over. Any honest version of this
company has to answer that question rather than route around it.

The answer is not higher fidelity — that is an arms race against physics that
nobody wins. The answer is **calibration**: run a large sim campaign, pair it
with a small number of matched hardware runs, and use *prediction-powered
inference* to produce a statistically valid bound on real-world performance.

This is published, solved method. **SureSim**
([arXiv:2510.04354](https://arxiv.org/abs/2510.04354) — Princeton, UT Austin,
Waymo, UCLA, October 2025) formalises combining real and simulated evaluations
as a prediction-powered inference problem, using a small number of paired
real/sim evaluations to rectify bias in large-scale simulation, and reports
saving 20–25% of hardware evaluation effort for equivalent bounds.

The method is free to build on. Almost nobody has productised it.

This is the moat, and critically it is a **data** moat rather than an
algorithmic one. Calibration requires paired sim/real observations. Those
accumulate per customer, per robot, per policy family, and are expensive for a
competitor to replicate from scratch. The sim-to-real gap stops being the
company's weakness and becomes its product.

### Layer 3 — The evidence

The notified-body package.

EU Machinery Regulation 2023/1230 applies from **20 January 2027**. Its Annex I
lists, among categories requiring **third-party conformity assessment**,
"safety components with fully or partially self-evolving behaviour using
machine learning approaches ensuring safety functions."

Read that carefully, because it is the whole regulatory thesis: a learned
policy performing a safety function **cannot be self-certified**. A notified
body has to sign it. And notified bodies currently have no settled methodology
for learned control — there is no established answer to "what evidence would
convince you this policy is safe?"

Whoever supplies the format they converge on is positioned extraordinarily
well. That is not a claim that we will; it is a statement of what the prize is.

Layer 3 is a near-automatic byproduct of Layers 1 and 2 — *provided the archive
format is designed for it now*. That is the main architectural constraint this
strategy places on the next six months of engineering.

### Why this order

Layer 3 is where the money is. But nobody buys compliance tooling seventeen
months early from a solo founder with no reference customers. Layer 1 is where
the usage is, and it is saleable today on pure engineering merit. Layer 2 is
what makes Layer 3 credible and is the part that cannot be copied.

**Sell 1. Build 2 quietly. 3 becomes inevitable.**

---

## 4. Why now

- **The regulatory clock is real and close.** EU MR 2023/1230 applies
  20 January 2027 — roughly five months from writing. ML-based safety
  components fall under third-party assessment.
  ([Nemko](https://digital.nemko.com/regulations/eu-machinery-regulation) ·
  [EU-OSHA](https://osha.europa.eu/en/legislation/directive/regulation-20231230eu-machinery) ·
  [Inkog Labs](https://inkog.io/labs/eu-machinery-regulation-ai-agents))

- **The buyers are extremely well funded.** $8.7B into humanoid robotics
  through July 2026 — 1.8× the whole of 2025. Figure has raised ~$2.34B at a
  ~$39B valuation; NEURA Robotics closed up to $1.4B at ~$7B in June 2026. 523
  robotics startups have raised seed as of August 2026.
  ([Humanoid Index](https://humanoidindex.org/funding) ·
  [TechFundingNews](https://techfundingnews.com/top-humanoid-robot-startups-2026-funding/))

- **The category is forecast to form in 2027 — not yet.** Independent 2026
  analyses predict policy evaluation emerging as a standalone product
  category in 2027, combining simulation, standardised benchmarks and automated
  regression testing, explicitly analogised to how software QA became its own
  profession and tooling market.
  ([SVRC State of Robotics 2026](https://www.roboticscenter.ai/state-of-robotics-2026))

That third point is the timing argument, and it cuts both ways. Six to twelve
months ahead of a forming category is the right amount early. Three years early
kills companies; six months late means competing with funded incumbents for
attention you can no longer get for free.

---

## 5. Competition

| Who | What they do | Why the gap survives |
| --- | --- | --- |
| **Applied Intuition** (~$15B) | Full AV stack — simulation, perception, data management | AV-shaped. Sells the simulator. Robotics is adjacent expansion, not focus |
| **Foretellix** | Scenario-based V&V, M-SDL, compliance workflows | Closest analogue, and genuinely good — but AV/ADAS, expanding toward warehouse AMR rather than learned-policy humanoids |
| **NVIDIA** — Isaac Sim 6.0, Isaac Lab 3.0, Newton 1.0 | The substrate everyone runs on. Adopted by 1X, Agility, Boston Dynamics, Figure, AgiBot | **A channel, not a competitor.** They sell GPUs and give the platform away. No incentive to own V&V evidence or statistical calibration |
| **Academia** — SureSim, RoboDojo, REALM, GigaWorld, WorldGym | Methods, benchmarks, world models | Publishes methods, free to adopt. Does not ship products, support, SLAs or audit trails |
| **In-house harnesses** | Every serious team has one | **The real competitor.** Beaten only by being dramatically better at one narrow thing |

### The structural choice

**Be simulator-agnostic and own the layer above the simulator.**

Do not build a simulator. That fight is lost before it starts, against a
company giving one away for free and shipping MuJoCo Warp inside Newton. Drive
*their* simulator harder than they do, and own the three things they have no
reason to want: the adversarial search, the statistical calibration, and the
evidence chain.

This single decision converts NVIDIA's ecosystem from an existential threat
into a distribution channel. It is the most important structural choice in this
document.

### On in-house harnesses

This is the competitor that actually kills the company, and it deserves more
than a table row. Every serious robotics team has an evaluation script. The
argument against building it in-house is not "ours is nicer" — it is:

1. **Adversarial search is not what they built.** In-house harnesses evaluate
   on a fixed suite. They answer "did it pass the tests we thought of?" not
   "what breaks it?"
2. **Calibration is a research project.** Layer 2 is a real statistical
   contribution to maintain, and no robotics team wants to staff it.
3. **Evidence is not a side project.** Third-party-defensible archives with
   reproducibility guarantees are a compliance product, not a script.

If we are only better at (1), we lose. The wedge is (1); the business is (2)
and (3).

---

## 6. Business model

**Unit: per robot program, per year.**

Not per seat — these teams are small, and seat pricing punishes exactly the
adoption we want. Not per simulation-hour — compute is commoditised, and
metered pricing perversely disincentivises the core behaviour of the product,
which is running *more* conditions.

> **The figures below are estimates.** They are anchored on published AV V&V
> deal sizes and on robotics companies' funding stages, not on quoted prices.
> Treat them as hypotheses to test against the first three customers, and
> expect to be wrong about at least one tier.

| Stage | Price (estimate) | What they get |
| --- | --- | --- |
| Design partner | $0, in exchange for paired sim/real data rights | Layer 1, hands-on |
| Pilot | $25–50K | One robot program, bounded campaign |
| Production | $75–250K/yr | Continuous CI, calibrated bounds |
| Certification pack | $50–150K one-off + services | Layer 3 evidence for a notified body |

The data-rights clause in the design-partner agreement is not a concession to
get the deal done. It is the most valuable term in the contract, because it is
the only way Layer 2 gets built.

---

## 7. Risks

Stated plainly, worst first.

1. **Sim-to-real is existential.** If failures found in simulation do not
   predict failures on hardware, this is theatre with good typography. Layer 2
   is the mitigation and it is not optional — which is why it is phase two of
   the roadmap and not a later nice-to-have. The honest position is that this
   risk is *managed*, never *eliminated*.

2. **In-house harnesses.** See above. Mitigation is narrowness: be
   overwhelmingly better at adversarial search and calibrated evidence, and
   resist every temptation to become a general simulation platform.

3. **NVIDIA absorbs the wedge.** If Isaac Lab ships policy regression testing,
   Layer 1 closes overnight. Mitigation: simulator-agnosticism, and owning the
   statistics and evidence layers that sell no GPUs.

4. **Solo is a credibility constraint.** Design partners will ask who owns the
   physics. This does not block the first two phases — both are buildable
   alone — but a robotics/controls co-founder or a named advisor materially
   changes the third. Worth starting on early precisely because the roadmap
   does not depend on it.

5. **Geography.** Building from Baku while selling EU conformity evidence is
   real friction, and an EU entity is likely a precondition for Layer 3 being
   sellable at all. Not urgent today. The failure mode is letting it become
   urgent without noticing.

6. **The category forms in 2027, not now.** If the forecast is wrong and it
   forms in 2029, Layer 1 has to carry the company alone for two years. Layer 1
   was chosen partly because it can.

---

## 8. The one artifact that matters

More than any document, deck, or feature:

> **A failure mode found in a real customer's policy, that they did not know
> about, which they then reproduced on hardware.**

Every phase of the roadmap exists to make that sentence true. Once it is true,
fundraising and sales both become straightforward. Until it is true, neither
does, and no amount of strategy compensates.

---

## Sources

- [Nemko — Guide to the 2027 EU Machinery Regulation](https://digital.nemko.com/regulations/eu-machinery-regulation)
- [EU-OSHA — Regulation 2023/1230/EU](https://osha.europa.eu/en/legislation/directive/regulation-20231230eu-machinery)
- [Inkog Labs — EU Machinery Regulation: AI compliance before January 2027](https://inkog.io/labs/eu-machinery-regulation-ai-agents)
- [Badithela et al. — Reliable and Scalable Robot Policy Evaluation with Imperfect Simulators (arXiv:2510.04354)](https://arxiv.org/abs/2510.04354)
- [Humanoid Index — funding tracker](https://humanoidindex.org/funding)
- [TechFundingNews — top humanoid robot startups 2026](https://techfundingnews.com/top-humanoid-robot-startups-2026-funding/)
- [SVRC — State of Robotics 2026](https://www.roboticscenter.ai/state-of-robotics-2026)
- [Contrary Research — Applied Intuition breakdown](https://research.contrary.com/company/applied-intuition)
- [NVIDIA — Isaac Lab](https://developer.nvidia.com/isaac/lab)
