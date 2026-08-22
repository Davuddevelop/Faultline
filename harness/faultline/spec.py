"""What a run is, before it happens.

A RunSpec is the complete, frozen description of one test: which robot, which
policy, what was perturbed, what counts as failure, and which seeds. It is
hashable and serialisable, and it is the only thing needed to reproduce a run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Perturbation:
    """One point in the parameter space.

    Every field is a physical quantity in a named unit. Nothing is normalised
    to 0-1: an assessor reading the record needs to see ``slope_deg=18``, not
    ``slope=0.72``.
    """

    push_impulse_ns: float = 0.0      # N.s, applied to the torso
    push_time_s: float = 1.0          # when the push lands
    push_yaw_deg: float = 0.0         # direction in the horizontal plane
    friction_mu: float | None = None  # None = leave the model's own value
    slope_deg: float = 0.0            # ground incline
    slope_yaw_deg: float = 0.0        # downhill direction
    sensor_lag_ms: float = 0.0        # observation delay seen by the policy
    torque_loss_pct: float = 0.0      # actuator strength lost, 0-100
    payload_kg: float = 0.0           # extra mass on the torso
    payload_offset_m: float = 0.0     # how far off centre that mass sits

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Predicate:
    """A rule the customer wrote. Never a learned classifier.

    ``signal`` names a scalar the runner computes each step; ``op`` and
    ``threshold`` decide when it counts as a violation.
    """

    name: str
    signal: str                       # tilt_deg | height_m | contact_force_n | joint_vel_rads
    op: str                           # ">" or "<"
    threshold: float
    grace_s: float = 0.0              # ignore violations before this time

    def __post_init__(self) -> None:
        if self.op not in (">", "<"):
            raise ValueError(f"predicate {self.name!r}: op must be '>' or '<', got {self.op!r}")
        if self.grace_s < 0:
            raise ValueError(f"predicate {self.name!r}: grace_s must not be negative")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Seeds:
    """Three seeds, recorded separately.

    A single global seed hides which component caused a divergence. Keeping
    them apart means a replay that differs can be traced to the sampler, the
    simulator or the policy.
    """

    sampler: int = 0
    sim: int = 0
    policy: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunSpec:
    model_path: str
    policy_id: str
    perturbation: Perturbation = field(default_factory=Perturbation)
    predicates: tuple[Predicate, ...] = ()
    seeds: Seeds = field(default_factory=Seeds)
    duration_s: float = 6.0
    control_hz: float = 50.0

    # ---- provenance -------------------------------------------------
    def model_hash(self) -> str:
        return hashlib.sha256(Path(self.model_path).read_bytes()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_path": self.model_path,
            "model_sha256": self.model_hash(),
            "policy_id": self.policy_id,
            "perturbation": self.perturbation.as_dict(),
            "predicates": [p.as_dict() for p in self.predicates],
            "seeds": self.seeds.as_dict(),
            "duration_s": self.duration_s,
            "control_hz": self.control_hz,
        }

    def config_hash(self) -> str:
        """Stable across dict ordering, so two identical specs hash alike."""
        blob = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def with_perturbation(self, **kw: Any) -> RunSpec:
        return replace(self, perturbation=replace(self.perturbation, **kw))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunSpec:
        """Rebuild a spec from a record, so a run can be replayed by someone
        who has only the JSON and the model file."""
        return cls(
            model_path=d["model_path"],
            policy_id=d["policy_id"],
            perturbation=Perturbation(**d["perturbation"]),
            predicates=tuple(Predicate(**p) for p in d["predicates"]),
            seeds=Seeds(**d["seeds"]),
            duration_s=d["duration_s"],
            control_hz=d["control_hz"],
        )
