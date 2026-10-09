"""Body poses for a 3D replay, recorded from the real runner loop.

The site's replay used to come from a script that re-implemented the
simulation loop for the ad. A copy drifts: it applied only the push, and a
runner fix would not reach it. This records through ``run(on_step=...)``, so a
replay is the run that produced the result, step for step.

The replay format is the one the Teeter site and app draw (``js/machine.js``):
per control step the torso's position and quaternion, then for each leg the
hip, thigh and calf body origins and the foot. It is specific to robots built
like the stand-in quadruped; for anything else ``quadruped_replay`` returns
None and callers fall back to the recorded signals, rather than drawing a
machine that is not the customer's.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from .policies import Policy
from .runner import Trajectory, run
from .spec import RunSpec

FORMAT = "teeter-replay/1"
LEGS = ("fr", "fl", "hr", "hl")
PARTS = ("hip", "thigh", "calf")
PUSH_WINDOW_S = 0.05            # runner.run spreads an impulse over this


def _ids(model: mujoco.MjModel) -> dict[str, Any] | None:
    """The bodies and geoms the replay needs, or None if this robot lacks them."""
    def body(name: str) -> int:
        return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)

    def geom(name: str) -> int:
        return mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)

    torso, torso_geom = body("torso"), geom("torso")
    legs = [[body(f"{leg}_{part}") for part in PARTS] for leg in LEGS]
    feet = [geom(f"{leg}_foot") for leg in LEGS]
    if min([torso, torso_geom, *feet, *(i for leg in legs for i in leg)]) < 0:
        return None
    if model.geom_type[torso_geom] != mujoco.mjtGeom.mjGEOM_BOX:
        return None
    return {"torso": torso, "torso_geom": torso_geom, "legs": legs, "feet": feet}


def record(spec: RunSpec, policy: Policy) -> tuple[Trajectory, list[list[float]], list[float]] | None:
    """Run ``spec`` once and keep one replay frame per control step.

    Returns the trajectory, the frames and the torso's half extents, or None
    when the robot is not built like the stand-in quadruped."""
    model = mujoco.MjModel.from_xml_path(spec.model_path)
    ids = _ids(model)
    if ids is None:
        return None
    frames: list[list[float]] = []

    def keep(t: float, m: mujoco.MjModel, d: mujoco.MjData) -> None:
        row = [round(float(v), 3) for v in d.xpos[ids["torso"]]]
        row += [round(float(v), 4) for v in d.xquat[ids["torso"]]]
        for leg, foot in zip(ids["legs"], ids["feet"]):
            for b in leg:
                row += [round(float(v), 3) for v in d.xpos[b]]
            row += [round(float(v), 3) for v in d.geom_xpos[foot]]
        frames.append(row)

    traj = run(spec, policy, on_step=keep)
    half = [float(v) for v in model.geom_size[ids["torso_geom"]]]
    return traj, frames, half


def quadruped_replay(minimal: RunSpec, policy: Policy, *, threshold: float,
                     speed: float = 0.5) -> dict[str, Any] | None:
    """A replay of a failure's minimal case beside the same robot unperturbed.

    The push shown is the requested impulse; the runner applies it on the
    control grid, so the robot receives a quantised amount (see runner.run).
    """
    caught = record(minimal, policy)
    if caught is None:
        return None
    nominal_spec = minimal.with_perturbation(
        push_impulse_ns=0.0, slope_deg=0.0, sensor_lag_ms=0.0, torque_loss_pct=0.0,
        payload_kg=0.0, payload_offset_m=0.0, friction_mu=None)
    nominal = record(nominal_spec, policy)
    assert nominal is not None
    runs = {}
    for label, (traj, frames, _half), spec in (("nominal", nominal, nominal_spec),
                                               ("minimal", caught, minimal)):
        runs[label] = {
            "push": spec.perturbation.push_impulse_ns,
            "perturbation": spec.perturbation.as_dict(),
            "tilt": [round(float(v), 2) for v in traj.tilt_deg],
            "f": frames,
        }
    return {
        "format": FORMAT,
        "hz": minimal.control_hz,
        "speed": speed,
        "push_t": minimal.perturbation.push_time_s,
        "window": PUSH_WINDOW_S,
        "threshold": threshold,
        "half": caught[2],
        "runs": runs,
    }


def supports_replay(model_path: str | Path) -> bool:
    return _ids(mujoco.MjModel.from_xml_path(str(model_path))) is not None


def _check_window() -> None:
    """The window above must stay the runner's. Read it from the source rather
    than importing a private name, so a change there fails loudly here."""
    src = (Path(__file__).parent / "runner.py").read_text()
    m = re.search(r"push_window = ([\d.]+)", src)
    if not m or float(m.group(1)) != PUSH_WINDOW_S:
        raise RuntimeError("capture.PUSH_WINDOW_S no longer matches runner.run's push window")


_check_window()
