---
name: optimisation-and-search
description: How the harness searches a continuous parameter space for failures — severity as a signed objective and why binary pass/fail cannot be optimised, the Cross-Entropy Method (not Covariance Matrix Adaptation), elite fitting, variance collapse and the floor that prevents it, and why a directed campaign's samples cannot be used to estimate a failure rate. Use when reading search.py, tuning a campaign budget, adding a search method, or interpreting what a hit rate does and does not mean.
metadata:
  origin: written for this repo
---

# Searching for failures

The problem: given a continuous space of physical conditions, find the points
where a policy violates a rule. The academic name for this is **falsification
of cyber-physical systems**, and the field has been at it since long before
this repo existed — S-TaLiRo and Breach are the canonical tools.

## Severity: the objective that makes search possible

A binary pass/fail gives a directed method nothing to climb. Every failing run
scores 1, every passing run 0, and the space between them carries no
information. So the objective is a **signed margin**:

```python
return float(window.max() - pred.threshold) if pred.op == ">" \
    else float(pred.threshold - window.min())      # predicates.py:56
```

Positive means the predicate fired. Negative is the remaining margin — how much
room was left. A run that reached 34° against a 35° threshold scores −1, and
that is far more informative than "passed": it says the boundary is right there.

This is the same idea the falsification literature calls **robustness
semantics** for temporal logic. Knowing the term is worth something in a
conversation with a researcher.

Two properties of this implementation:

- It is evaluated over the **whole trajectory** after a grace period, not the
  final state. A policy that breaches at t=3 and recovers by t=6 has breached.
- It **saturates**. Once the robot has fully toppled, every fallen run scores
  about the same. That is deliberate: it makes the objective discriminate near
  the boundary rather than rewarding the search for pushing deeper into a
  region it has already found.

## Two methods

**Random** samples uniformly from the space. It is the honest baseline, and the
only one whose samples support a rate estimate (see below).

**CEM** — the **Cross-Entropy Method**. Get the name right: it is *not*
Covariance Matrix Adaptation (CMA-ES), which is a different algorithm. CEM fits
a distribution to the best-scoring samples and resamples from it.

```python
mean = (lo + hi) / 2.0     # start centred
std  = span / 4.0          # ±2σ spans the declared range
floor = span * min_std_frac
```

Each round: sample, evaluate, keep the top `elite_frac` by severity, refit mean
and standard deviation to those, repeat. Round 0 is uniform, so the search
starts unbiased.

```python
k = max(2, int(round(len(usable) * elite_frac)))
elite = np.array([... sorted(usable, key=severity, reverse=True)[:k]])
mean = elite.mean(axis=0)
std = np.maximum(elite.std(axis=0), floor)    # search.py:329–335
```

Defaults: `elite_frac=0.25`, `iterations=6`, `min_std_frac=0.08`.

It is an **adaptive sampler, not a trained adversary**. No gradients, no
training run, deterministic from its seed. Describe it that way — calling it a
learned or trained adversary overstates what it is.

## Three properties worth knowing

**The variance floor is load-bearing.** Without `min_std_frac`, the fitted
standard deviation shrinks every round — the elite of a concentrated
distribution is more concentrated still — and after a few rounds it collapses
onto a single point. The search then re-evaluates essentially the same
condition until the budget runs out. The floor keeps it exploring.

**The Gaussian is diagonal.** One standard deviation per axis, no covariance
term. So the fitted distribution is always axis-aligned and cannot represent a
correlated failure region — a diagonal ridge where "high slope with low
friction" fails though neither alone does. CEM will still find such a region,
but it models it as a fat blob spanning both axes. This is a real limitation,
and it is precisely where CMA-ES, which does estimate a covariance matrix,
would behave differently.

**Invalid runs are excluded from the fit.** A diverged run gets
`severity = -inf`, so it sorts last naturally — but if an entire round
diverges, the elite would be all `-inf` and the mean would become `nan`,
poisoning every subsequent round:

```python
usable = [s for s in round_samples if not s.invalid]
if not usable:
    continue          # keep the previous distribution
```

## Parallelism and determinism

Rounds are sequential because each fit depends on the whole previous round.
Within a round, evaluations are independent and run across workers. That
ordering is what keeps a parallel campaign **bit-identical to a serial one** —
a property worth preserving in any new search method, and one the tests pin by
comparing fingerprints.

## The statistical trap: CEM hit rates are not failure rates

This is the most important thing in this file.

CEM deliberately concentrates its samples where failures are dense. That is the
entire point, and it is why a directed campaign finds failures at a much higher
rate than uniform sampling on the same budget.

**It also means CEM's samples are not a uniform sample of the space.** They are
drawn from an adaptive distribution that was steered toward failure. So:

> A CEM hit rate is a statement about the search, not about the robot.

You may report a directed-vs-uniform hit rate as a comparison of **methods**.
You may not report the directed figure as "the policy fails X% of the time" —
that is a claim about the space, and only uniformly drawn samples support it.
Conflating the two is the easiest available way to make this product's numbers
indefensible.

If a failure *rate* is what is wanted, it must come from the random-search arm,
with an interval attached.

## Coverage

Coverage is measured by binning the space into a grid and counting occupied
cells (`report.py`, `bins=4` by default). The module says outright that this is
blunt: six axes at four bins each is 4096 cells, and a few hundred samples
cannot fill it.

Report it as what it is — the fraction of a coarse grid over the **declared**
space that was visited. It is not a coverage guarantee, and low coverage under
a directed search is expected rather than a defect.

## Related

`uncertainty-and-evidence` covers what these numbers license you to claim.
`robot-policy-testing` covers reducing a raw failing run to a minimal case.
