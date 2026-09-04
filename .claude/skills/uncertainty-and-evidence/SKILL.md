---
name: uncertainty-and-evidence
description: What a campaign's numbers actually license you to claim — binomial confidence intervals and the rule of three, why finding no failures is not evidence of safety, sampling bias from directed search, coverage versus confidence, determinism versus statistical variation, and prediction-powered inference for combining simulation with scarce hardware runs. Use when writing a report or safety appendix, quoting a hit rate or coverage figure, reviewing marketing copy, or deciding how many runs a claim needs.
metadata:
  origin: written for this repo
---

# What the numbers let you say

This project's entire value is that its output survives someone hostile reading
it. Every overstated claim is a liability, and the overstatements are almost
always statistical rather than deliberate. This file is the discipline for that.

## Determinism first: what kind of uncertainty this is

A crucial distinction, because it inverts the usual intuition.

**A single run has no measurement noise.** Given the same config and the same
three seeds, the trajectory is bit-identical — the tests pin this. Re-running a
campaign does not give you a distribution to average over.

So uncertainty here is **not** about noisy measurement. It is entirely about
**sampling**: we evaluated a few hundred points from a continuous volume
containing infinitely many, and the question is what those points say about the
ones we did not evaluate.

This has a practical consequence. Running the same campaign ten times tells you
nothing new. Running it with ten different sampler seeds tells you how stable
the *search* is. Those are different questions and should be labelled as such.

## The binomial basics

For uniformly sampled runs, "does the policy fail here" is a Bernoulli trial.
With `k` failures in `n` uniform samples, the estimated rate is `k/n` — and it
needs an interval.

Use a **Wilson interval**, not the normal approximation. The textbook
`p̂ ± 1.96·√(p̂(1−p̂)/n)` breaks badly when `p̂` is near 0 or 1, which is exactly
where safety-relevant rates live. At `k=0` it gives an interval of zero width,
which is nonsense.

**The rule of three** is the one to memorise. If you observe **zero** failures
in `n` independent uniform trials, the 95% upper bound on the true rate is
approximately:

> **3 / n**

So 300 clean runs bound the failure rate below roughly 1%. Not zero — 1%. And
1,000 runs still only bound it below 0.3%. This single fact is the fastest way
to explain why "we ran it a hundred times and it was fine" is a weak claim, and
why demonstrating rare-event safety by sampling is brutally expensive.

## Directed search breaks the arithmetic

Everything above requires **uniform** samples. CEM samples are not uniform —
they are drawn from a distribution deliberately steered toward failure.

So a CEM campaign supports statements like "the directed search found failures
that uniform sampling at this budget did not." It does **not** support a rate,
an interval, or a probability. If a rate is needed, it comes from the random
arm. See `optimisation-and-search` for the full argument.

## Coverage is not confidence

Two different quantities that get conflated in exactly the wrong direction:

- **Coverage** — the fraction of a coarse grid over the *declared* space that
  was visited. A geometric statement about where we looked.
- **Confidence** — a statistical statement about a rate.

High coverage does not imply a low failure rate, and low coverage does not
imply the results are worthless. Also note that coverage is bounded by the
declared space: 100% coverage of a space that omits the condition that kills
the robot is 100% of the wrong thing. Always state the space alongside the
coverage figure.

## What a minimal case is, and is not

Reduction relaxes perturbations toward nominal until the violation stops
firing, and reports the smallest condition that still breaks the policy. Two
honest limits:

- It reduces **one axis at a time**, so it finds a locally minimal case, not a
  global minimum. A different reduction order could yield a different case.
- The reported values are **requested** values. As `control-theory` documents,
  the impulse and lag axes quantise on the control grid, so the delivered
  quantity differs — at the default push time, a requested impulse
  over-delivers by 20%. Never quote a minimal impulse to three significant
  figures as though it were what the robot received.

## The claims ladder

Defensible:

- "Under the declared parameter space, the directed search found N failure
  modes; the smallest condition reproducing mode 1 is X."
- "Uniform sampling at n runs found k failures; the 95% interval on the rate
  is [a, b]."
- "This result re-runs to a bit-identical trajectory on this simulator build
  and platform."
- "Zero failures in n uniform runs bounds the rate below roughly 3/n."

Not defensible, ever:

- "The policy is safe." The harness finds failures; it cannot show their
  absence.
- "Verified", "validated", "certified", "compliant."
- "This satisfies a notified body." Nobody can currently say what does — the
  delegated act defining adequate evidence under EU MR 2023/1230 is not due
  until 2028.
- Any rate derived from directed-search samples.

The asymmetry to keep in mind: **finding a failure is strong evidence; finding
none is weak evidence.** One counterexample disproves a claim of robustness
outright. A thousand clean runs bound a rate loosely and prove nothing about
the region you did not sample.

## Combining simulation with scarce hardware runs

The interesting open direction, and the reason the calibration layer is worth
building. Simulation is cheap and biased; hardware is expensive and truthful.
Naively averaging them inherits the bias; using hardware alone is
unaffordable.

**Prediction-powered inference** resolves this: use a large simulated sample
plus a small set of *paired* real runs to correct the simulator's bias, and
obtain intervals that are statistically valid even though the simulator is
wrong. The relevant work is **SureSim** — Badithela et al., *Reliable and
Scalable Robot Policy Evaluation with Imperfect Simulators*,
[arXiv:2510.04354](https://arxiv.org/abs/2510.04354) — cited in
`docs/strategy.md` and `docs/primer.md`.

**This is not built.** It is the Phase C layer. Describe it as a direction,
never as a capability.

## Before publishing any number

1. Was it produced by uniform or directed sampling? Only uniform supports a
   rate.
2. Does it have an interval? A point estimate from a few hundred samples is
   not a finding.
3. Is the declared space stated next to it? A coverage or rate figure without
   its space is meaningless.
4. Is it a requested or a delivered quantity? For impulse and lag, they differ.
5. Is it illustrative rather than measured? Then label it illustrative, in the
   same sentence.
6. Does any word in the sentence imply safety, verification or compliance? Cut
   it.

## Related

`optimisation-and-search` covers why directed samples are biased.
`robot-policy-testing` covers the reproducibility record and the regulatory
framing.
