"""The versioned contracts between the app, the API and the runner.

campaign spec   teeter.campaign/1   what to search, against what, for what
evaluation      teeter.evaluation/1 one simulation, as the runner streams it
result          teeter.result/1     what a finished campaign hands back

The API does not import the engine, so the axis table and the signal list are
restated here. ``tests/test_contracts.py`` imports the engine and fails if the
two ever disagree; the repo has shipped numbers that drifted from the code
before, and this is where that would happen next.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SPEC_VERSION = "teeter.campaign/1"
RESULT_VERSION = "teeter.result/1"

# name -> (unit, nominal, reduction tolerance, quantised on the control grid)
# Mirrors SEVERITY_AXES in harness/faultline/reduce.py. Friction's nominal is
# the model's own value, so it is None here and comes back with each result.
AXES: dict[str, tuple[str, float | None, float, bool]] = {
    "push_impulse_ns": ("N.s", 0.0, 0.5, True),
    "slope_deg": ("deg", 0.0, 0.25, False),
    "sensor_lag_ms": ("ms", 0.0, 2.5, True),
    "torque_loss_pct": ("%", 0.0, 1.0, False),
    "payload_kg": ("kg", 0.0, 0.05, False),
    "payload_offset_m": ("m", 0.0, 0.005, False),
    "friction_mu": ("-", None, 0.02, False),
}
# Mirrors the fields of Trajectory in harness/faultline/runner.py. A rule can
# see these and nothing else.
SIGNALS: tuple[str, ...] = ("tilt_deg", "height_m", "contact_force_n", "joint_vel_rads")

AxisName = Literal["push_impulse_ns", "slope_deg", "sensor_lag_ms", "torque_loss_pct",
                   "payload_kg", "payload_offset_m", "friction_mu"]
SignalName = Literal["tilt_deg", "height_m", "contact_force_n", "joint_vel_rads"]

_NAME = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")


def _name(v: str, what: str) -> str:
    if not _NAME.match(v):
        raise ValueError(f"{what} {v!r} must be lowercase letters, digits, '_' or '-', starting with a letter")
    return v


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Seeds(_Strict):
    """Three seeds, kept separate: one global seed hides which component
    caused a divergence on replay."""
    sampler: int = 0
    sim: int = 0
    policy: int = 0


class Predicate(_Strict):
    name: str
    signal: SignalName
    op: Literal[">", "<"]
    threshold: float
    grace_s: float = Field(0.0, ge=0.0, le=60.0)

    @field_validator("name")
    @classmethod
    def _n(cls, v: str) -> str:
        return _name(v, "predicate name")

    def sentence(self) -> str:
        verb = "rises above" if self.op == ">" else "falls below"
        tail = f", ignoring the first {self.grace_s:g} s" if self.grace_s else ""
        return f"Fail when {self.signal} {verb} {self.threshold:g}{tail}."


class Search(_Strict):
    method: Literal["cem", "random"] = "cem"
    budget: int = Field(150, ge=1, le=100_000)
    target: str | None = None          # a predicate name; the first when unset
    workers: int = Field(1, ge=-1, le=1024)   # -1: every core the runner has


class Reduce(_Strict):
    enabled: bool = True
    max: int = Field(10, ge=1, le=200)
    budget: int = Field(200, ge=1, le=10_000)


class CampaignSpec(_Strict):
    """A campaign, as data. Robots and policies are named, not located: the
    runner resolves names against its own allowlist, so the server can never
    point a customer's machine at an arbitrary file or module."""
    version: Literal["teeter.campaign/1"] = SPEC_VERSION
    robot: str
    policy: str
    duration_s: float = Field(5.0, gt=0.0, le=120.0)
    control_hz: float = Field(50.0, ge=1.0, le=2000.0)
    seeds: Seeds = Field(default_factory=Seeds)
    axes: dict[AxisName, tuple[float, float]]
    predicates: list[Predicate] = Field(min_length=1, max_length=16)
    search: Search = Field(default_factory=Search)
    reduce: Reduce = Field(default_factory=Reduce)
    bins: int = Field(4, ge=2, le=16)
    base_body: str | None = None
    observation: list[Any] = Field(default_factory=list)

    @field_validator("robot", "policy")
    @classmethod
    def _names(cls, v: str) -> str:
        return _name(v, "name")

    @model_validator(mode="after")
    def _coherent(self) -> "CampaignSpec":
        if not self.axes:
            raise ValueError("axes: declare at least one axis to search")
        for axis, (lo, hi) in self.axes.items():
            if not (math.isfinite(lo) and math.isfinite(hi)) or not hi > lo:
                raise ValueError(f"axes.{axis}: the upper bound must exceed the lower, got [{lo}, {hi}]")
            if axis == "torque_loss_pct" and not (0 <= lo and hi < 100):
                raise ValueError("axes.torque_loss_pct: must lie within [0, 100)")
            if axis == "friction_mu" and lo <= 0:
                raise ValueError("axes.friction_mu: friction must be positive")
            if axis in ("push_impulse_ns", "slope_deg", "sensor_lag_ms", "payload_kg", "payload_offset_m") and lo < 0:
                raise ValueError(f"axes.{axis}: a magnitude cannot be negative")
        names = [p.name for p in self.predicates]
        if len(set(names)) != len(names):
            raise ValueError("predicates: names must be unique")
        if self.search.target is not None and self.search.target not in names:
            raise ValueError(f"search.target {self.search.target!r} is not a predicate; declared: {', '.join(names)}")
        return self

    def experiment(self) -> dict[str, Any]:
        """Everything that must match for two campaigns to be compared: the
        spec without the policy, which is the thing a gate varies."""
        d = self.model_dump(mode="json")
        d.pop("policy")
        return d

    def experiment_sha256(self) -> str:
        blob = json.dumps(self.experiment(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


class EvaluationIn(_Strict):
    """One simulation as the runner streams it. ``severity`` is None for an
    invalid run (the solver diverged): -inf does not survive JSON."""
    index: int = Field(ge=0)
    iteration: int = Field(0, ge=0)
    perturbation: dict[str, float]
    severity: float | None
    failed: bool
    invalid: str | None = None
    violation: dict[str, Any] | None = None


class ModeIn(_Strict):
    label: str
    predicate: str
    required: list[str]
    count: int = Field(ge=1)
    minimal: dict[str, Any]                  # the full minimal perturbation
    first_t: float
    peak: float | None = None
    locally_minimal: bool
    evaluations: int = Field(ge=0)
    region: dict[str, Any] = Field(default_factory=dict)
    replay: str | None = None                # artifact names, uploaded first
    trace: str | None = None


class ResultIn(_Strict):
    """What a finished campaign hands back. Large things (replays, traces) are
    artifacts, uploaded before this and referred to by name."""
    version: Literal["teeter.result/1"] = RESULT_VERSION
    harness: str
    environment: dict[str, str]
    robot: dict[str, Any]                    # name, sha256, summary
    policy: dict[str, Any]                   # name, id (content-derived)
    base_config_sha256: str
    nominals: dict[str, float]               # per axis, friction from the model
    evaluations: int
    failures: int
    invalid: int
    first_failure_index: int | None
    elapsed_s: float
    reduced: int
    coverage: dict[str, Any]
    modes: list[ModeIn]
