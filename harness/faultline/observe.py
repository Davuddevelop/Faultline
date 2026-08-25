"""What the policy sees.

The runner used to build one observation: ``concatenate([qpos, qvel])``. No
customer's policy expects that. A policy is a function of a specific vector in
a specific order with specific units, and feeding it a different layout does
not raise — it produces confident, wrong actions, and the campaign reports
failures that belong to the harness rather than the robot.

So the layout is declared, ordered, and printable. ``describe()`` exists so a
customer can diff our layout against their training code before spending an
afternoon on a campaign that was mismapped from the first step.

Term names follow the conventions used by Isaac Lab and legged_gym, because
that is what most locomotion policies are trained against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .model import RobotModel


class ObservationError(ValueError):
    """Raised with the offending term named."""


# kind -> (width function, needs a floating base)
_KINDS: dict[str, tuple[Any, bool]] = {
    "joint_pos":         (lambda r: r.n_joints,     False),
    "joint_vel":         (lambda r: r.n_joints,     False),
    "base_quat":         (lambda r: 4,              True),
    "base_lin_vel":      (lambda r: 3,              True),
    "base_ang_vel":      (lambda r: 3,              True),
    "projected_gravity": (lambda r: 3,              True),
    "prev_action":       (lambda r: r.n_actuators,  False),
    "qpos":              (lambda r: -1,             False),   # resolved at build
    "qvel":              (lambda r: -1,             False),
    "constant":          (lambda r: -1,             False),
}


@dataclass(frozen=True)
class Term:
    kind: str
    scale: float = 1.0
    relative: bool = False              # joint_pos only: offset by the default pose
    values: tuple[float, ...] = ()      # constant only

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ObservationError(
                f"unknown observation term {self.kind!r}; available: "
                + ", ".join(sorted(_KINDS))
            )
        if self.kind == "constant" and not self.values:
            raise ObservationError("a 'constant' term needs values, e.g. [1.0, 0.0, 0.0]")
        if self.relative and self.kind != "joint_pos":
            raise ObservationError(f"'relative' applies to joint_pos, not {self.kind!r}")

    def width(self, robot: RobotModel) -> int:
        if self.kind == "constant":
            return len(self.values)
        if self.kind == "qpos":
            return int(robot.model.nq)
        if self.kind == "qvel":
            return int(robot.model.nv)
        return _KINDS[self.kind][0](robot)


@dataclass(frozen=True)
class ObservationSpec:
    """An ordered layout. Order is the contract, so it is never sorted."""

    terms: tuple[Term, ...]

    def __post_init__(self) -> None:
        if not self.terms:
            raise ObservationError("an observation needs at least one term")

    # ── construction ──────────────────────────────────────────────────

    @staticmethod
    def default() -> "ObservationSpec":
        """What a locomotion policy usually consumes. Explicit, not implied."""
        return ObservationSpec((
            Term("projected_gravity"),
            Term("base_ang_vel"),
            Term("joint_pos", relative=True),
            Term("joint_vel", scale=0.05),
        ))

    @staticmethod
    def raw() -> "ObservationSpec":
        """The harness's historical layout, kept so old configs still mean
        what they meant."""
        return ObservationSpec((Term("qpos"), Term("qvel")))

    @staticmethod
    def from_list(items: list[Any]) -> "ObservationSpec":
        terms: list[Term] = []
        for i, it in enumerate(items):
            if isinstance(it, str):
                terms.append(Term(it))
            elif isinstance(it, dict):
                unknown = set(it) - {"term", "scale", "relative", "values"}
                if unknown:
                    raise ObservationError(
                        f"observation[{i}]: unknown key(s) {', '.join(sorted(unknown))}"
                    )
                if "term" not in it:
                    raise ObservationError(f"observation[{i}]: missing 'term'")
                terms.append(Term(
                    kind=it["term"],
                    scale=float(it.get("scale", 1.0)),
                    relative=bool(it.get("relative", False)),
                    values=tuple(float(v) for v in it.get("values", ())),
                ))
            else:
                raise ObservationError(
                    f"observation[{i}] must be a name or a mapping, got {type(it).__name__}"
                )
        return ObservationSpec(tuple(terms))

    # ── use ───────────────────────────────────────────────────────────

    def validate(self, robot: RobotModel) -> None:
        """Fail before the campaign, not during it."""
        for t in self.terms:
            if _KINDS[t.kind][1] and not robot.free_base:
                raise ObservationError(
                    f"term {t.kind!r} needs a floating base, but {robot.base_body!r} is "
                    "fixed to the world. A bolted-down robot has no base motion to "
                    "observe — drop the term, or check the base was resolved correctly."
                )

    def size(self, robot: RobotModel) -> int:
        return sum(t.width(robot) for t in self.terms)

    def describe(self, robot: RobotModel) -> str:
        """The layout, index by index. Diff this against your training code."""
        rows, i = [], 0
        for t in self.terms:
            w = t.width(robot)
            tag = t.kind + (" (relative)" if t.relative else "")
            scale = "" if t.scale == 1.0 else f"  x{t.scale:g}"
            rows.append(f"  [{i:3d}:{i + w:3d}]  {tag}{scale}")
            i += w
        rows.append(f"  total {i}")
        return "\n".join(rows)

    def build(self, robot: RobotModel, data, prev_action: np.ndarray) -> np.ndarray:
        m = robot.model
        parts: list[np.ndarray] = []
        # body->world rotation of the base; its transpose takes world into body
        R = data.xmat[robot.base_body_id].reshape(3, 3)

        for t in self.terms:
            if t.kind == "joint_pos":
                v = data.qpos[robot.qpos_adr]
                if t.relative:
                    v = v - m.qpos0[robot.qpos_adr]
            elif t.kind == "joint_vel":
                v = data.qvel[robot.dof_adr]
            elif t.kind == "base_quat":
                v = data.qpos[3:7]
            elif t.kind == "base_lin_vel":
                v = R.T @ data.qvel[0:3]          # qvel[0:3] is world frame
            elif t.kind == "base_ang_vel":
                v = data.qvel[3:6]                 # already body frame in MuJoCo
            elif t.kind == "projected_gravity":
                v = R.T @ np.array([0.0, 0.0, -1.0])
            elif t.kind == "prev_action":
                v = prev_action
            elif t.kind == "qpos":
                v = data.qpos
            elif t.kind == "qvel":
                v = data.qvel
            else:                                  # constant
                v = np.asarray(t.values, dtype=float)
            parts.append(np.asarray(v, dtype=float).ravel() * t.scale)

        return np.concatenate(parts)
