"""Turning a campaign into the two documents and the archive.

The interesting problem here is what a "failure mode" is. Listing 308 failures
by count tells a customer nothing and invites them to argue with the number.
Grouping them needs a signature that is explainable, deterministic, and not a
learned classifier — because the moment a black box decides what counts as the
same failure, the evidence stops being checkable.

The signature used is the *reduced* form of each failure: which predicate
fired, and which axes turned out to be genuinely required once everything
irrelevant was relaxed away. "Fails on push alone" and "fails on slope and
payload together" are different modes; two runs that reduce to the same
required set are the same mode at different magnitudes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .policies import Policy
from .reduce import ReductionResult, reduce_failure
from .runner import run, sim_environment
from .search import CampaignResult, Sample
from .space import SearchSpace
from .spec import RunSpec

SCHEMA_VERSION = 1


@dataclass
class FailureMode:
    """A group of failures that reduce to the same required axes."""

    predicate: str
    required: tuple[str, ...]
    members: list[Sample]
    exemplar: ReductionResult          # the minimal reproducing case

    @property
    def label(self) -> str:
        return f"{self.predicate} via {' + '.join(self.required) if self.required else 'no axis'}"

    def region(self, space: SearchSpace) -> dict[str, dict[str, float]]:
        """The box the members of this mode occupy, per required axis."""
        out: dict[str, dict[str, float]] = {}
        for axis in self.required:
            vals = [m.perturbation[axis] for m in self.members if axis in m.perturbation]
            if not vals:
                continue
            out[axis] = {
                "min": round(float(np.min(vals)), 4),
                "median": round(float(np.median(vals)), 4),
                "max": round(float(np.max(vals)), 4),
                "unit": space.unit(axis),
            }
        return out

    def as_dict(self, space: SearchSpace) -> dict[str, Any]:
        return {
            "label": self.label,
            "predicate": self.predicate,
            "required_axes": list(self.required),
            "count": len(self.members),
            "region": self.region(space),
            "minimal_case": self.exemplar.minimal_spec.perturbation.as_dict(),
            "minimal_case_locally_minimal": self.exemplar.locally_minimal,
        }


@dataclass
class Coverage:
    """How much of the declared space was actually visited.

    The grid occupancy is deliberately blunt: with six axes even four bins each
    is 4096 cells, and a few hundred samples cannot fill it. Stating that
    plainly is the point — an assessor is entitled to know the campaign
    sampled a volume, not swept it.
    """

    space: SearchSpace
    bins: int
    cells_total: int
    cells_visited: int
    per_axis: dict[str, dict[str, float]]

    @property
    def fraction(self) -> float:
        return self.cells_visited / self.cells_total if self.cells_total else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "bins_per_axis": self.bins,
            "cells_total": self.cells_total,
            "cells_visited": self.cells_visited,
            "fraction_visited": round(self.fraction, 6),
            "per_axis": self.per_axis,
        }


def measure_coverage(campaign: CampaignResult, bins: int = 4) -> Coverage:
    space = campaign.space
    axes = space.axes
    lo, hi = space.lo(), space.hi()

    per_axis: dict[str, dict[str, float]] = {}
    for i, axis in enumerate(axes):
        vals = np.array([s.perturbation[axis] for s in campaign.samples])
        per_axis[axis] = {
            "declared_min": round(float(lo[i]), 4),
            "declared_max": round(float(hi[i]), 4),
            "sampled_min": round(float(vals.min()), 4),
            "sampled_max": round(float(vals.max()), 4),
            "unit": space.unit(axis),
        }

    pts = np.array([[s.perturbation[a] for a in axes] for s in campaign.samples])
    idx = np.clip(((pts - lo) / (hi - lo) * bins).astype(int), 0, bins - 1)
    visited = {tuple(row) for row in idx}

    return Coverage(
        space=space, bins=bins, cells_total=bins ** len(axes),
        cells_visited=len(visited), per_axis=per_axis,
    )


@dataclass
class Report:
    campaign: CampaignResult
    spec: RunSpec
    modes: list[FailureMode]
    coverage: Coverage
    reduced_count: int
    failures_total: int
    environment: dict[str, str] = field(default_factory=sim_environment)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "campaign": {
                "method": self.campaign.method,
                "seed": self.campaign.seed,
                "budget": self.campaign.budget,
                "target_predicate": self.campaign.target_predicate,
                "failures_total": self.failures_total,
                "base_config_sha256": self.campaign.base_config_sha256,
            },
            "space": self.campaign.space.as_dict(),
            "coverage": self.coverage.as_dict(),
            "failures_reduced": self.reduced_count,
            "modes": [m.as_dict(self.campaign.space) for m in self.modes],
            "environment": self.environment,
            "created_at": self.created_at,
        }


def build_report(
    campaign: CampaignResult,
    spec: RunSpec,
    policy: Policy,
    *,
    max_reduce: int = 12,
    reduce_budget: int = 200,
    bins: int = 4,
) -> Report:
    """Reduce the most severe failures, group them by what they actually need.

    Only the ``max_reduce`` most severe failures are minimised — reduction
    costs a couple of dozen simulations each, and reducing all 300 failures of
    a campaign would cost more than the campaign did. The report states how
    many were reduced so the grouping is never mistaken for exhaustive.
    """
    if max_reduce < 1:
        raise ValueError("max_reduce must be at least 1")

    failures = sorted(campaign.failures, key=lambda s: s.severity, reverse=True)
    chosen = failures[:max_reduce]

    grouped: dict[tuple[str, tuple[str, ...]], FailureMode] = {}
    for sample in chosen:
        reduced = reduce_failure(
            spec.with_perturbation(**sample.perturbation),
            policy,
            target_predicate=campaign.target_predicate,
            budget=reduce_budget,
        )
        key = (reduced.target_predicate, tuple(sorted(reduced.required)))
        if key in grouped:
            grouped[key].members.append(sample)
        else:
            grouped[key] = FailureMode(
                predicate=key[0], required=key[1], members=[sample], exemplar=reduced
            )

    modes = sorted(grouped.values(), key=lambda m: len(m.members), reverse=True)

    return Report(
        campaign=campaign, spec=spec, modes=modes,
        coverage=measure_coverage(campaign, bins=bins),
        reduced_count=len(chosen), failures_total=len(campaign.failures),
    )


# ─────────────────────────── the deliverables ───────────────────────────

def _region_line(axis: str, r: dict[str, float]) -> str:
    return (f"  {axis:<20} {r['min']:>9.4g} .. {r['max']:<9.4g} "
            f"median {r['median']:<9.4g} {r['unit']}")


def engineering_report(report: Report) -> str:
    """For the team that trained the policy: what broke, and the smallest
    condition that breaks it."""
    c, sp = report.campaign, report.campaign.space
    out = [
        "# Engineering report",
        "",
        f"Campaign `{c.method}` seed {c.seed}, {c.budget} simulations, "
        f"target predicate `{c.target_predicate}`.",
        f"{report.failures_total} runs violated it. "
        f"The {report.reduced_count} most severe were minimised and grouped below.",
        "",
        "## Failure modes",
        "",
    ]

    if not report.modes:
        out += ["No violations were found. This bounds nothing: it means this "
                "budget, in this space, did not find one.", ""]
    for i, m in enumerate(report.modes, 1):
        ex = m.exemplar
        out += [
            f"### {i}. {m.label}",
            "",
            f"{len(m.members)} of the {report.reduced_count} reduced failures need "
            f"{' and '.join(m.required) if m.required else 'no axis'}.",
            "",
            "**Minimal reproducing case**",
            "",
            "```",
        ]
        for axis in m.required:
            val = getattr(ex.minimal_spec.perturbation, axis)
            out.append(f"{axis:<20} {val:.4g} {sp.unit(axis)}")
        out += [
            f"{'-> ' + ex.minimal_violation.predicate:<20} first fires at "
            f"t={ex.minimal_violation.first_t:.2f}s",
            "```",
            "",
            f"Locally minimal: `{ex.locally_minimal}` "
            f"({ex.evaluations} simulations). Relaxing any listed axis further "
            "stops the failure; a different combination might still be smaller.",
            "",
            "**Region occupied by this mode**",
            "",
            "```",
        ]
        region = m.region(sp)
        out += [_region_line(a, r) for a, r in region.items()] or ["  (none)"]
        out += ["```", ""]

    out += [
        "## What this does not say",
        "",
        "- Modes are grouped by which axes each failure needs after reduction. "
        "Two runs in one group fail for the same reason in this sense and no other.",
        f"- Only the {report.reduced_count} most severe of {report.failures_total} "
        "failures were reduced. The grouping is not exhaustive.",
        "- No claim is made that the policy is safe. This campaign found failures; "
        "it cannot show their absence.",
        "",
    ]
    return "\n".join(out)


def safety_appendix(report: Report) -> str:
    """For someone assessing the evidence who did not build any of it."""
    c, sp = report.campaign, report.campaign.space
    cov = report.coverage
    out = [
        "# Safety case appendix",
        "",
        f"Generated {report.created_at}.",
        "",
        "## Method",
        "",
        "A campaign samples points in a declared parameter space, executes each in "
        "deterministic simulation, and evaluates explicit predicates over the whole "
        "trajectory. A run is flagged only when a predicate written by the "
        "manufacturer evaluates true. No learned classifier sits between a run and "
        "its verdict.",
        "",
        f"Sampling method: `{c.method}`. Budget: {c.budget} simulations. "
        f"Sampler seed: {c.seed}.",
        "",
        "## Predicates evaluated",
        "",
        "| name | signal | condition | grace |",
        "| --- | --- | --- | --- |",
    ]
    for p in report.spec.predicates:
        out.append(f"| `{p.name}` | `{p.signal}` | `{p.op} {p.threshold}` | {p.grace_s}s |")

    out += [
        "",
        f"The campaign targeted `{c.target_predicate}`.",
        "",
        "## Declared parameter space",
        "",
        "| axis | declared | sampled | unit |",
        "| --- | --- | --- | --- |",
    ]
    for axis, a in cov.per_axis.items():
        out.append(
            f"| `{axis}` | {a['declared_min']:g} .. {a['declared_max']:g} "
            f"| {a['sampled_min']:g} .. {a['sampled_max']:g} | {a['unit']} |"
        )

    out += [
        "",
        "## Coverage",
        "",
        f"Partitioning each of the {sp.dims} axes into {cov.bins} bins gives "
        f"{cov.cells_total} cells. {c.budget} simulations visited "
        f"**{cov.cells_visited}** of them — **{cov.fraction:.2%}**.",
        "",
        "This campaign sampled the declared volume; it did not sweep it. Any "
        "statement about behaviour in unvisited regions is unsupported by this "
        "evidence.",
        "",
        "## Reproducibility",
        "",
        f"Base configuration SHA-256: `{c.base_config_sha256}`",
        "",
        "| component | version |",
        "| --- | --- |",
    ]
    for k, v in sorted(report.environment.items()):
        out.append(f"| {k} | `{v}` |")

    out += [
        "",
        "Every run in the archive carries its seeds, the resolved configuration and "
        "a trajectory digest, and can be re-executed independently. Results are "
        "reproducible bit for bit within one simulator build and CPU architecture; "
        "across architectures small numerical differences are expected and the "
        "recorded environment is what makes that distinguishable from a defect.",
        "",
        "## Limits of this evidence",
        "",
        "- Findings apply to the declared space above and to no conditions outside it.",
        "- Absence of a violation in an unvisited region is not evidence of safety there.",
        "- Minimal cases are locally minimal: no single axis can be relaxed further, "
        "but a different combination may be smaller.",
        "- This document does not assert conformity with any regulation or standard.",
        "",
    ]
    return "\n".join(out)


def write_archive(report: Report, policy: Policy, directory: str | Path,
                  *, traces_for_modes: bool = True) -> Path:
    """Seeds, configuration and verdict for every run, plus a trajectory trace
    for each mode's minimal case."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    manifest = directory / "manifest.jsonl"
    with manifest.open("w") as fh:
        for s in report.campaign.samples:
            resolved = report.spec.with_perturbation(**s.perturbation)
            fh.write(json.dumps({
                "index": s.index,
                "iteration": s.iteration,
                "config_sha256": resolved.config_hash(),
                "model_sha256": resolved.model_hash(),
                "policy_id": report.spec.policy_id,
                "seeds": report.spec.seeds.as_dict(),
                "perturbation": {k: round(v, 6) for k, v in s.perturbation.items()},
                "severity": round(s.severity, 6),
                "verdict": "fail" if s.failed else "pass",
                "violation": s.violation.as_dict() if s.violation else None,
            }, sort_keys=True) + "\n")

    (directory / "campaign.json").write_text(
        json.dumps(report.campaign.as_dict(), indent=2, sort_keys=True) + "\n"
    )
    (directory / "report.json").write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n"
    )

    if traces_for_modes:
        traces = directory / "traces"
        traces.mkdir(exist_ok=True)
        # A previous campaign with more modes leaves mode-N.csv files behind.
        # Left in place they describe modes this report does not contain, and an
        # archive whose contents disagree with its own report.json is worse than
        # no archive. Only the files this function writes are removed.
        for stale in traces.glob("mode-*.csv"):
            stale.unlink()
        for i, m in enumerate(report.modes, 1):
            traj = run(m.exemplar.minimal_spec, policy)
            rows = ["t,tilt_deg,height_m,contact_force_n,joint_vel_rads"]
            rows += [
                f"{t:.4f},{a:.6f},{b:.6f},{c_:.6f},{d:.6f}"
                for t, a, b, c_, d in zip(
                    traj.t, traj.tilt_deg, traj.height_m,
                    traj.contact_force_n, traj.joint_vel_rads
                )
            ]
            (traces / f"mode-{i}.csv").write_text("\n".join(rows) + "\n")

    return directory


def write_deliverables(report: Report, policy: Policy, directory: str | Path) -> Path:
    """All three: the engineering report, the appendix, and the archive."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "engineering-report.md").write_text(engineering_report(report))
    (directory / "safety-appendix.md").write_text(safety_appendix(report))
    write_archive(report, policy, directory / "archive")
    return directory
