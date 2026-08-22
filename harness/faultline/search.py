"""Choosing which points to run.

Random sampling covers the declared volume. The directed method concentrates
its budget where violations are dense. Both spend exactly the budget they are
given, both are reproducible from a seed, and `compare()` runs them against
each other across several seeds without pretending a handful of seeds is a
significance test.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .policies import Policy
from .predicates import Violation, evaluate, severity
from .runner import run, sim_environment
from .space import SearchSpace
from .spec import Predicate, RunSpec

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Sample:
    index: int                       # order within the campaign
    perturbation: dict[str, float]
    severity: float
    failed: bool
    violation: Violation | None = None
    iteration: int = 0               # which directed round produced it

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "iteration": self.iteration,
            "perturbation": {k: round(v, 6) for k, v in self.perturbation.items()},
            "severity": round(self.severity, 6),
            "failed": self.failed,
            "violation": self.violation.as_dict() if self.violation else None,
        }


@dataclass
class CampaignResult:
    method: str
    space: SearchSpace
    seed: int
    budget: int
    target_predicate: str
    samples: list[Sample]
    elapsed_s: float
    base_config_sha256: str
    environment: dict[str, str] = field(default_factory=sim_environment)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def failures(self) -> list[Sample]:
        return [s for s in self.samples if s.failed]

    @property
    def first_failure_index(self) -> int | None:
        """How many runs were spent before the first violation — the number a
        customer paying per simulation actually cares about."""
        return next((s.index for s in self.samples if s.failed), None)

    @property
    def worst(self) -> Sample | None:
        return max(self.samples, key=lambda s: s.severity, default=None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "method": self.method,
            "seed": self.seed,
            "budget": self.budget,
            "target_predicate": self.target_predicate,
            "space": self.space.as_dict(),
            "base_config_sha256": self.base_config_sha256,
            "failures_found": len(self.failures),
            "first_failure_index": self.first_failure_index,
            "elapsed_s": round(self.elapsed_s, 3),
            "samples": [s.as_dict() for s in self.samples],
            "environment": self.environment,
            "created_at": self.created_at,
        }

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n")
        return path

    def summary(self) -> str:
        first = self.first_failure_index
        return (
            f"{self.method:<8} seed={self.seed}  "
            f"failures {len(self.failures):>3}/{self.budget}  "
            f"first at {'-' if first is None else first:>4}  "
            f"best severity {self.worst.severity if self.worst else float('nan'):+7.1f}  "
            f"{self.elapsed_s:5.1f}s"
        )


def _target(spec: RunSpec, name: str | None) -> Predicate:
    if not spec.predicates:
        raise ValueError("the base spec declares no predicates; nothing to search for")
    if name is None:
        return spec.predicates[0]
    for p in spec.predicates:
        if p.name == name:
            return p
    known = ", ".join(p.name for p in spec.predicates)
    raise ValueError(f"predicate {name!r} is not on this spec; declared: {known}")


def _evaluate_point(
    spec: RunSpec, policy: Policy, pred: Predicate, kwargs: dict[str, float], index: int,
    iteration: int = 0,
) -> Sample:
    """One point. Uses run() + evaluate() rather than execute(): building a
    full RunRecord for every sample is wasted work at hundreds of runs, and
    records are built later only for the failures worth keeping."""
    candidate = spec.with_perturbation(**kwargs)
    traj = run(candidate, policy)
    hit = next((v for v in evaluate(traj, candidate.predicates) if v.predicate == pred.name), None)
    return Sample(
        index=index,
        perturbation=kwargs,
        severity=severity(traj, pred),
        failed=hit is not None,
        violation=hit,
        iteration=iteration,
    )


def random_search(
    spec: RunSpec, policy: Policy, space: SearchSpace, *, budget: int = 150, seed: int = 0,
    target_predicate: str | None = None,
) -> CampaignResult:
    """Uniform coverage of the declared volume. The baseline every directed
    method has to beat to justify its complexity."""
    if budget < 1:
        raise ValueError("budget must be at least 1")
    pred = _target(spec, target_predicate)
    rng = np.random.default_rng(seed)

    t0 = time.perf_counter()
    samples = [
        _evaluate_point(spec, policy, pred, space.sample(rng), i)
        for i in range(budget)
    ]
    return CampaignResult(
        method="random", space=space, seed=seed, budget=budget,
        target_predicate=pred.name, samples=samples,
        elapsed_s=time.perf_counter() - t0,
        base_config_sha256=spec.config_hash(),
    )


def cem_search(
    spec: RunSpec, policy: Policy, space: SearchSpace, *, budget: int = 150, seed: int = 0,
    target_predicate: str | None = None, elite_frac: float = 0.25,
    iterations: int = 6, min_std_frac: float = 0.08,
) -> CampaignResult:
    """Cross-entropy method: fit a Gaussian to the most severe samples and
    resample from it, so budget concentrates where violations are dense.

    This is an adaptive sampler, not a trained adversary. It needs no
    gradients and no training run, and it is deterministic from its seed.

    `min_std_frac` is a variance floor. Without it the fitted distribution
    collapses onto a single point after a few rounds and the search stops
    exploring entirely.
    """
    if budget < 1:
        raise ValueError("budget must be at least 1")
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if not 0 < elite_frac <= 1:
        raise ValueError("elite_frac must be in (0, 1]")

    pred = _target(spec, target_predicate)
    rng = np.random.default_rng(seed)
    lo, hi = space.lo(), space.hi()
    span = hi - lo

    mean = (lo + hi) / 2.0
    std = span / 4.0
    floor = span * min_std_frac

    per_round = max(1, budget // iterations)
    samples: list[Sample] = []
    index = 0
    t0 = time.perf_counter()

    for it in range(iterations):
        remaining = budget - index
        if remaining <= 0:
            break
        n = min(per_round, remaining)
        if it == iterations - 1:
            n = remaining                      # spend every last evaluation

        if it == 0:
            points = rng.uniform(lo, hi, size=(n, space.dims))
        else:
            points = space.clip(rng.normal(mean, std, size=(n, space.dims)))

        round_samples = []
        for row in points:
            round_samples.append(
                _evaluate_point(spec, policy, pred, space.to_kwargs(row), index, iteration=it)
            )
            index += 1
        samples.extend(round_samples)

        # refit to the elite of this round
        k = max(2, int(round(len(round_samples) * elite_frac)))
        elite = np.array(
            [[s.perturbation[a] for a in space.axes]
             for s in sorted(round_samples, key=lambda s: s.severity, reverse=True)[:k]]
        )
        mean = elite.mean(axis=0)
        std = np.maximum(elite.std(axis=0), floor)

    return CampaignResult(
        method="cem", space=space, seed=seed, budget=budget,
        target_predicate=pred.name, samples=samples,
        elapsed_s=time.perf_counter() - t0,
        base_config_sha256=spec.config_hash(),
    )


METHODS: dict[str, Callable[..., CampaignResult]] = {
    "random": random_search,
    "cem": cem_search,
}


@dataclass
class ComparisonResult:
    """Per-seed results for each method, and nothing stronger.

    A handful of seeds at a low failure rate is a description, not a
    significance test, and the summary says so rather than implying a winner.
    """

    campaigns: dict[str, list[CampaignResult]]
    budget: int
    seeds: list[int]

    def stat(self, method: str, fn: Callable[[CampaignResult], float]) -> list[float]:
        return [fn(c) for c in self.campaigns[method]]

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"budget": self.budget, "seeds": self.seeds, "methods": {}}
        for name, runs in self.campaigns.items():
            found = [len(c.failures) for c in runs]
            firsts = [c.first_failure_index for c in runs]
            out["methods"][name] = {
                "failures_per_seed": found,
                "failures_median": statistics.median(found),
                "first_failure_per_seed": firsts,
                "best_severity_per_seed": [round(c.worst.severity, 3) for c in runs],
            }
        return out

    def summary(self) -> str:
        lines = [f"budget {self.budget} per seed, {len(self.seeds)} seeds: {self.seeds}", ""]
        for name, runs in self.campaigns.items():
            found = [len(c.failures) for c in runs]
            firsts = [c.first_failure_index for c in runs]
            shown = ["-" if f is None else str(f) for f in firsts]
            lines.append(
                f"  {name:<8} failures per seed {found}  "
                f"median {statistics.median(found):>5.1f}   first failure at {shown}"
            )
        lines.append(
            f"\n  {len(self.seeds)} seeds is a description, not a significance test."
        )
        return "\n".join(lines)


def compare(
    spec: RunSpec, policy: Policy, space: SearchSpace, *, budget: int = 150,
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4), methods: tuple[str, ...] = ("random", "cem"),
    target_predicate: str | None = None,
) -> ComparisonResult:
    """Run every method on every seed. Same space, same budget, same base spec."""
    for m in methods:
        if m not in METHODS:
            raise ValueError(f"unknown method {m!r}; available: {', '.join(METHODS)}")

    campaigns = {
        m: [
            METHODS[m](spec, policy, space, budget=budget, seed=s,
                       target_predicate=target_predicate)
            for s in seeds
        ]
        for m in methods
    }
    return ComparisonResult(campaigns=campaigns, budget=budget, seeds=list(seeds))
