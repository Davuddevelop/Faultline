"""What a run leaves behind.

A RunRecord is the unit the report and the archive are both built from. It
carries the verdict, the violation that produced it, and enough provenance
that someone who does not trust us can run it again.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .predicates import Violation, evaluate
from .policies import Policy
from .runner import Trajectory, run, sim_environment
from .spec import RunSpec

SCHEMA_VERSION = 1


@dataclass
class RunRecord:
    spec: RunSpec
    violations: list[Violation]
    trajectory_digest: str
    environment: dict[str, str]
    peaks: dict[str, float]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def failed(self) -> bool:
        return bool(self.violations)

    @property
    def verdict(self) -> str:
        return "fail" if self.failed else "pass"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "verdict": self.verdict,
            "config_sha256": self.spec.config_hash(),
            "trajectory_sha256": self.trajectory_digest,
            "spec": self.spec.as_dict(),
            "violations": [v.as_dict() for v in self.violations],
            "peaks": {k: round(v, 6) for k, v in self.peaks.items()},
            "environment": self.environment,
            "created_at": self.created_at,
        }

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n")
        return path


@dataclass
class ReplayResult:
    """The outcome of re-running a record. ``matched`` is the claim the safety
    case rests on."""

    matched: bool
    expected_digest: str
    actual_digest: str
    model_matched: bool
    environment_matched: bool
    notes: list[str]


def replay(record_path: str | Path, policy: Policy) -> ReplayResult:
    """Re-run a recorded run and check it lands in the same place.

    A mismatch is not necessarily a bug: MuJoCo results can differ across
    library versions and CPU architectures. The result reports whether the
    model and environment also differ, so the cause can be attributed instead
    of guessed at.
    """
    doc = json.loads(Path(record_path).read_text())
    spec = RunSpec.from_dict(doc["spec"])

    notes: list[str] = []
    if policy.id != doc["spec"]["policy_id"]:
        notes.append(
            f"policy differs: record has {doc['spec']['policy_id']!r}, "
            f"replaying with {policy.id!r}"
        )

    model_matched = spec.model_hash() == doc["spec"]["model_sha256"]
    if not model_matched:
        notes.append("model file has changed since the run was recorded")

    env_now = sim_environment()
    env_matched = env_now == doc["environment"]
    if not env_matched:
        differing = [k for k in env_now if env_now.get(k) != doc["environment"].get(k)]
        notes.append("environment differs in: " + ", ".join(sorted(differing)))

    traj = run(spec, policy)
    actual = traj.digest()
    expected = doc["trajectory_sha256"]

    if actual != expected and env_matched and model_matched:
        notes.append(
            "digest differs with an identical model and environment — this is a "
            "determinism bug, not drift"
        )

    return ReplayResult(
        matched=actual == expected,
        expected_digest=expected,
        actual_digest=actual,
        model_matched=model_matched,
        environment_matched=env_matched,
        notes=notes,
    )


def execute(spec: RunSpec, policy: Policy) -> tuple[RunRecord, Trajectory]:
    """Run once and record it. The trajectory is returned alongside so callers
    can plot or reduce without re-running."""
    traj = run(spec, policy)
    violations = evaluate(traj, spec.predicates)

    record = RunRecord(
        spec=spec,
        violations=violations,
        trajectory_digest=traj.digest(),
        environment=sim_environment(),
        peaks={
            "tilt_deg": float(traj.tilt_deg.max()),
            "height_m_min": float(traj.height_m.min()),
            "contact_force_n": float(traj.contact_force_n.max()),
            "joint_vel_rads": float(traj.joint_vel_rads.max()),
        },
    )
    return record, traj
