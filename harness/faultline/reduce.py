"""Minimising a failing run.

A raw failing run perturbs several axes at once and is a poor bug report: the
customer cannot tell which of them mattered. Reduction relaxes each axis back
toward nominal for as long as the failure survives, so what gets reported is
the smallest condition that still breaks the policy.

The result is *locally* minimal — no single axis can be relaxed further — not
globally minimal. That distinction is carried in the record rather than glossed
over.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import mujoco

from .policies import Policy
from .predicates import Violation, evaluate
from .runner import run, sim_environment
from .spec import RunSpec

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Axis:
    """A perturbation field that has a magnitude worth minimising.

    ``nominal`` is the value at which the axis stops perturbing anything.
    ``None`` means the nominal is whatever the model itself specifies, which is
    only the case for friction.
    """

    field: str
    nominal: float | None
    tolerance: float
    unit: str


# push_time_s, push_yaw_deg and slope_yaw_deg are deliberately absent: they are
# *when* and *which direction*, not *how much*. Relaxing them toward zero would
# change the case rather than shrink it.
SEVERITY_AXES: tuple[Axis, ...] = (
    Axis("push_impulse_ns", 0.0, 0.5, "N.s"),
    Axis("slope_deg", 0.0, 0.25, "deg"),
    Axis("sensor_lag_ms", 0.0, 2.5, "ms"),
    Axis("torque_loss_pct", 0.0, 1.0, "%"),
    Axis("payload_kg", 0.0, 0.05, "kg"),
    Axis("payload_offset_m", 0.0, 0.005, "m"),
    Axis("friction_mu", None, 0.02, "-"),
)


class ReductionError(RuntimeError):
    """Raised when a run cannot be reduced, rather than returning something
    that looks like a reduction but is not."""


@lru_cache(maxsize=8)
def _model_friction(model_path: str) -> float:
    """The friction the model itself specifies — the nominal for that axis.

    Relaxing a slippery-floor failure means moving friction *up*, so the target
    has to come from the model rather than from zero.
    """
    model = mujoco.MjModel.from_xml_path(model_path)
    floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    return float(model.geom_friction[floor if floor >= 0 else 0, 0])


@dataclass
class AxisOutcome:
    field: str
    unit: str
    original: float | None
    minimal: float | None
    status: str          # eliminated | required | untouched

    def as_dict(self) -> dict[str, Any]:
        return {
            "axis": self.field,
            "unit": self.unit,
            "original": self.original,
            "minimal": self.minimal,
            "status": self.status,
        }


@dataclass
class ReductionResult:
    original_spec: RunSpec
    minimal_spec: RunSpec
    target_predicate: str
    original_violation: Violation
    minimal_violation: Violation
    axes: list[AxisOutcome]
    evaluations: int
    budget: int
    budget_exhausted: bool
    locally_minimal: bool
    environment: dict[str, str] = field(default_factory=sim_environment)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def eliminated(self) -> list[str]:
        """Axes that turned out to be irrelevant. Usually the headline of the
        bug report: not "it fell under six perturbations" but "it falls on an
        8 degree slope, and the rest did not matter"."""
        return [a.field for a in self.axes if a.status == "eliminated"]

    @property
    def required(self) -> list[str]:
        return [a.field for a in self.axes if a.status == "required"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "target_predicate": self.target_predicate,
            "original_config_sha256": self.original_spec.config_hash(),
            "minimal_config_sha256": self.minimal_spec.config_hash(),
            "original_perturbation": self.original_spec.perturbation.as_dict(),
            "minimal_perturbation": self.minimal_spec.perturbation.as_dict(),
            "original_violation": self.original_violation.as_dict(),
            "minimal_violation": self.minimal_violation.as_dict(),
            "axes": [a.as_dict() for a in self.axes],
            "eliminated": self.eliminated,
            "required": self.required,
            "evaluations": self.evaluations,
            "budget": self.budget,
            "budget_exhausted": self.budget_exhausted,
            "locally_minimal": self.locally_minimal,
            "environment": self.environment,
            "created_at": self.created_at,
        }

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n")
        return path

    def table(self) -> str:
        rows = [f"{'axis':<20}{'original':>10}{'minimal':>10}   status"]
        for a in self.axes:
            o = "unset" if a.original is None else f"{a.original:.3g}"
            m = "unset" if a.minimal is None else f"{a.minimal:.3g}"
            rows.append(f"{a.field:<20}{o:>10}{m:>10}   {a.status}")
        rows.append(
            f"\nevaluations {self.evaluations}/{self.budget}   "
            f"locally_minimal={self.locally_minimal}   "
            f"predicate={self.target_predicate}"
        )
        return "\n".join(rows)


def _violation(spec: RunSpec, policy: Policy, target: str) -> Violation | None:
    """One probe: does this perturbation still fire the predicate we are
    preserving? Any *other* predicate firing does not count — reducing into a
    different failure mode is not reducing this one."""
    for v in evaluate(run(spec, policy), spec.predicates):
        if v.predicate == target:
            return v
    return None


def reduce_failure(
    spec: RunSpec,
    policy: Policy,
    *,
    target_predicate: str | None = None,
    budget: int = 200,
    max_passes: int = 3,
) -> ReductionResult:
    """Relax perturbations toward nominal while the failure survives.

    Axes are minimised one at a time and the reduced value is kept before the
    next axis is tried, because the axes are coupled: relaxing the slope may
    permit further relaxing of the push. Passes repeat until nothing moves.
    """
    if budget < 1:
        raise ValueError("budget must be at least 1")

    used = 0

    def probe(candidate: RunSpec) -> Violation | None:
        nonlocal used
        used += 1
        return _violation(candidate, policy, target_predicate)

    # ---- establish what we are preserving ---------------------------------
    baseline = evaluate(run(spec, policy), spec.predicates)
    used += 1
    if not baseline:
        raise ReductionError(
            "cannot reduce a run that did not fail: no predicate fired"
        )
    if target_predicate is None:
        target_predicate = baseline[0].predicate      # earliest violation
    original_violation = next(
        (v for v in baseline if v.predicate == target_predicate), None
    )
    if original_violation is None:
        fired = ", ".join(sorted(v.predicate for v in baseline)) or "none"
        raise ReductionError(
            f"predicate {target_predicate!r} did not fire in this run; fired: {fired}"
        )

    current = spec
    exhausted = False
    converged = False

    for _ in range(max_passes):
        moved = False

        # largest first, normalised by each axis's own tolerance so that
        # degrees and kilograms can be compared at all
        def distance(ax: Axis) -> float:
            v = getattr(current.perturbation, ax.field)
            if v is None:
                return 0.0
            nom = ax.nominal if ax.nominal is not None else _model_friction(current.model_path)
            return abs(v - nom) / ax.tolerance

        for ax in sorted(SEVERITY_AXES, key=distance, reverse=True):
            value = getattr(current.perturbation, ax.field)
            if value is None:                       # friction left unset
                continue
            nominal = ax.nominal if ax.nominal is not None else _model_friction(current.model_path)
            if abs(value - nominal) <= ax.tolerance:
                continue

            if used >= budget:
                exhausted = True
                break

            # can the axis go away entirely?
            if probe(current.with_perturbation(**{ax.field: ax.nominal})) is not None:
                current = current.with_perturbation(**{ax.field: ax.nominal})
                moved = True
                continue

            # otherwise bisect: lo does not fire, hi does
            lo, hi = nominal, value
            while abs(hi - lo) > ax.tolerance:
                if used >= budget:
                    exhausted = True
                    break
                mid = (lo + hi) / 2.0
                if probe(current.with_perturbation(**{ax.field: mid})) is not None:
                    hi = mid
                else:
                    lo = mid

            if abs(hi - value) > ax.tolerance:
                current = current.with_perturbation(**{ax.field: hi})
                moved = True
            if exhausted:
                break

        if exhausted:
            break
        if not moved:
            converged = True
            break

    minimal_violation = probe(current)
    if minimal_violation is None:      # should be unreachable; never guess
        raise ReductionError(
            "internal: the reduced case no longer fires the target predicate"
        )

    axes: list[AxisOutcome] = []
    for ax in SEVERITY_AXES:
        before = getattr(spec.perturbation, ax.field)
        after = getattr(current.perturbation, ax.field)
        at_nominal = after is None or after == ax.nominal

        if at_nominal and (before is None or before == ax.nominal):
            status = "untouched"        # never perturbed in the first place
        elif at_nominal:
            status = "eliminated"       # was perturbed, turned out not to matter
        else:
            status = "required"         # still needed, whether or not it shrank
        axes.append(AxisOutcome(ax.field, ax.unit, before, after, status))

    return ReductionResult(
        original_spec=spec,
        minimal_spec=current,
        target_predicate=target_predicate,
        original_violation=original_violation,
        minimal_violation=minimal_violation,
        axes=axes,
        evaluations=used,
        budget=budget,
        budget_exhausted=exhausted,
        locally_minimal=converged and not exhausted,
    )
