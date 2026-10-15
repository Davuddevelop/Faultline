"""Two demo checkpoints for the gate demo. Not trained policies.

Each holds one pose, like the harness's built-in ``stand``, offset at the
hips and knees. They exist so the gate has two checkpoints that really differ
in physics, measured, not asserted: held against a push alone, with nothing
else perturbed, the stand-in quadruped breaches tilt_deg > 35.0 at

    stand    7.62 N.s requested       (the keyframe pose)
    Tall     6.29 N.s requested       hips -0.3 rad, knees +0.6 rad: centre of mass higher
    Crouch   8.83 N.s requested       hips +0.15 rad, knees -0.3 rad: centre of mass lower

(measured by bisection to 0.05 N.s on 9 October 2026). Reduction resolves a
push to 0.5 N.s, so Tall's difference from stand is wide enough to show as
widened every time.
"""

from __future__ import annotations

from pathlib import Path

import faultline
import mujoco

from faultline.policies import StandPolicy

MODEL = Path(faultline.__file__).resolve().parents[1] / "models" / "quadruped.xml"


class _Pose(StandPolicy):
    hip = 0.0
    knee = 0.0
    label = "pose"

    def __init__(self) -> None:
        ctrl = mujoco.MjModel.from_xml_path(str(MODEL)).key_ctrl[0].copy()
        ctrl[1::3] += self.hip           # actuators are abd, hip, knee per leg
        ctrl[2::3] += self.knee
        super().__init__(ctrl, name=self.label)


class Tall(_Pose):
    hip, knee, label = -0.3, 0.6, "tall-v2"


class Crouch(_Pose):
    hip, knee, label = 0.15, -0.3, "crouch-v3"
