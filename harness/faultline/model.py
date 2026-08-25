"""Loading somebody else's robot.

Until now the runner assumed our stand-in quadruped: a body literally named
``torso``, a floating base, and a keyframe to reset to. None of that holds for
a customer's model, and each assumption fails differently — a missing keyframe
raises, a missing ``torso`` raises, but a fixed base silently shifts every
joint index by six and produces plausible nonsense.

This module resolves those facts from the model itself and states them, so the
rest of the harness can stop guessing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import mujoco
import numpy as np


class ModelError(ValueError):
    """Raised with the offending detail named, rather than a stack trace."""


# MuJoCo joint type codes, named so the checks below read as prose.
_FREE = mujoco.mjtJoint.mjJNT_FREE
_BALL = mujoco.mjtJoint.mjJNT_BALL


@dataclass
class RobotModel:
    """A loaded model plus the facts the runner needs to stop hardcoding."""

    path: str
    model: mujoco.MjModel
    base_body: str
    base_body_id: int
    free_base: bool
    actuated_joints: tuple[str, ...]
    qpos_adr: np.ndarray          # qpos index per actuated joint
    dof_adr: np.ndarray           # qvel/dof index per actuated joint
    n_actuators: int
    has_keyframe: bool
    source_sha256: str
    notes: tuple[str, ...] = field(default=())

    @property
    def n_joints(self) -> int:
        return len(self.actuated_joints)

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "source_sha256": self.source_sha256,
            "base_body": self.base_body,
            "free_base": self.free_base,
            "n_joints": self.n_joints,
            "n_actuators": self.n_actuators,
            "has_keyframe": self.has_keyframe,
            "actuated_joints": list(self.actuated_joints),
        }

    def summary(self) -> str:
        base = "floating" if self.free_base else "fixed"
        return (
            f"{Path(self.path).name}: {self.n_joints} actuated joint(s), "
            f"{self.n_actuators} actuator(s), {base} base at {self.base_body!r}"
            f"{'' if self.has_keyframe else ', no keyframe'}"
        )


def _body_names(model: mujoco.MjModel) -> list[str]:
    return [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) or f"<body {i}>"
        for i in range(model.nbody)
    ]


def _resolve_base(model: mujoco.MjModel, requested: str | None) -> tuple[int, bool]:
    """Which body carries the robot, and is it free to move?

    Named explicitly when the caller knows. Otherwise the body with a free
    joint, since that is the floating base by definition; failing that the
    first child of the world, which is the convention for a fixed base.
    """
    if requested is not None:
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, requested)
        if bid < 0:
            raise ModelError(
                f"no body named {requested!r} in this model. "
                f"Bodies present: {', '.join(_body_names(model)[1:]) or '(none)'}"
            )
        return bid, _is_free(model, bid)

    for bid in range(1, model.nbody):
        if _is_free(model, bid):
            return bid, True

    children = [b for b in range(1, model.nbody) if model.body_parentid[b] == 0]
    if not children:
        raise ModelError("this model has no bodies attached to the world")
    return children[0], False


def _is_free(model: mujoco.MjModel, bid: int) -> bool:
    n, adr = model.body_jntnum[bid], model.body_jntadr[bid]
    return any(model.jnt_type[adr + j] == _FREE for j in range(n))


def load(path: str | Path, *, base_body: str | None = None) -> RobotModel:
    """Load a URDF or MJCF and resolve what the runner needs to know."""
    path = Path(path)
    if not path.exists():
        raise ModelError(f"no such model file: {path}")

    try:
        model = mujoco.MjModel.from_xml_path(str(path))
    except Exception as exc:                       # mujoco raises bare ValueError
        raise ModelError(f"{path.name} did not load: {exc}") from exc

    base_id, free_base = _resolve_base(model, base_body)

    # Actuated joints are the ones a policy can drive: every joint that is not
    # the free base. Ball joints are excluded because one actuator cannot
    # address three rotational degrees of freedom.
    actuated: list[str] = []
    qpos_adr: list[int] = []
    dof_adr: list[int] = []
    notes: list[str] = []
    n_ball = 0
    for j in range(model.njnt):
        jt = model.jnt_type[j]
        if jt == _FREE:
            continue
        if jt == _BALL:
            n_ball += 1
            continue
        actuated.append(
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, j) or f"<joint {j}>"
        )
        qpos_adr.append(int(model.jnt_qposadr[j]))
        dof_adr.append(int(model.jnt_dofadr[j]))

    if not actuated:
        raise ModelError(
            f"{path.name} has no hinge or slide joints, so there is nothing for a "
            "policy to drive. A rigid object cannot be tested this way."
        )
    if model.nu == 0:
        raise ModelError(
            f"{path.name} declares no actuators. A URDF converted straight to MJCF "
            "usually has none — add an <actuator> section naming the joints to drive."
        )

    if n_ball:
        notes.append(f"{n_ball} ball joint(s) ignored: one actuator cannot drive three DOF")
    if model.nu != len(actuated):
        notes.append(
            f"{model.nu} actuator(s) against {len(actuated)} actuated joint(s) — "
            "fine if deliberate, worth checking if not"
        )
    if model.nkey == 0:
        notes.append(
            "no <keyframe>, so there is no nominal pose to reset to; the run starts "
            "from the model's default configuration"
        )
    if path.suffix.lower() == ".urdf":
        notes.append(
            "URDF carries no contact parameters and no actuator dynamics worth "
            "trusting — check friction, damping and gear ratios before believing a result"
        )

    return RobotModel(
        path=str(path),
        model=model,
        base_body=mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, base_id) or "<base>",
        base_body_id=base_id,
        free_base=free_base,
        actuated_joints=tuple(actuated),
        qpos_adr=np.array(qpos_adr, dtype=int),
        dof_adr=np.array(dof_adr, dtype=int),
        n_actuators=int(model.nu),
        has_keyframe=model.nkey > 0,
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        notes=tuple(notes),
    )
