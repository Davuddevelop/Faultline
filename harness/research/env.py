"""A training environment for the stand-in quadruped, built to match how Teeter tests it.

It reuses the harness's own model loader, observation layout, push model and
fall rule, so a brain trained here sees what Teeter will show it:
  * observation: ObservationSpec.default(), 30 wide
  * action: 12 joint targets = stance + ACTION_SCALE * a, with a in [-1, 1]
  * control rate 50 Hz; a push is an impulse spread over 0.05 s on the base
  * a fall is tilt_deg > 35 or height_m < 0.12, the campaign's two rules

Research tooling only. Nothing here changes what Teeter measures.
"""
from __future__ import annotations

from pathlib import Path

import mujoco
import numpy as np

from faultline.model import load as load_model
from faultline.runner import _apply_perturbation
from faultline.spec import Perturbation, RunSpec
from faultline.observe import ObservationSpec

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")
CONTROL_HZ = 50.0
PUSH_WINDOW_S = 0.05
ACTION_SCALE = 0.3          # rad around the stance; exported inside the ONNX graph
TILT_LIMIT_DEG = 35.0
FALLEN_HEIGHT_M = 0.12
EPISODE_STEPS = 200         # 4 s


class StandEnv:
    def __init__(self, sampler=None, seed: int = 0) -> None:
        """sampler: f(rng) -> dict of Perturbation fields, or None for no perturbation."""
        self.sampler = sampler
        self.robot = load_model(MODEL, base_body=None)
        self.model = self.robot.model
        self.data = mujoco.MjData(self.model)
        self.obs_spec = ObservationSpec.default()
        self.obs_spec.validate(self.robot)
        self.stance = np.array(self.model.key_ctrl[0], dtype=float)
        self.steps_per_ctrl = max(1, round((1.0 / CONTROL_HZ) / self.model.opt.timestep))
        self.n_obs = self.obs_spec.size(self.robot)
        self.n_act = self.model.nu
        self.rng = np.random.default_rng(seed)

    def reset(self) -> np.ndarray:
        kw = dict(self.sampler(self.rng)) if self.sampler else {}
        self.push_t = float(self.rng.uniform(0.5, 1.5))
        self.lag_steps = int(round(kw.get("sensor_lag_ms", 0.0) / 1000.0 * CONTROL_HZ))
        kw.pop("sensor_lag_ms", None)
        # conditions that change the model (slope, motors, payload) need a fresh copy
        # each episode, built by the harness's own function so training and testing agree
        if any(kw.get(k) for k in ("slope_deg", "torque_loss_pct", "payload_kg", "friction_mu")):
            self.robot = load_model(MODEL, base_body=None)
            self.model = self.robot.model
            spec = RunSpec(MODEL, "train", Perturbation(**{k: v for k, v in kw.items() if k != "push_impulse_ns"}))
            _apply_perturbation(self.model, spec, self.robot.base_body_id)
            self.data = mujoco.MjData(self.model)
        elif self.model.opt.gravity[2] != -9.81 or self.model.actuator_forcerange[0, 1] != 18.0:
            self.robot = load_model(MODEL, base_body=None)      # last episode was perturbed; start clean
            self.model = self.robot.model
            self.data = mujoco.MjData(self.model)
        mujoco.mj_resetDataKeyframe(self.model, self.data, 0)
        self.k = 0
        self.prev_a = np.zeros(self.n_act)
        self.push_force = np.zeros(6)
        mag = kw.get("push_impulse_ns", 0.0) / PUSH_WINDOW_S
        if mag > 0:
            yaw = float(self.rng.uniform(0.0, 2 * np.pi))
            self.push_force[:3] = [mag * np.cos(yaw), mag * np.sin(yaw), 0.0]
        self.hist = []
        return self._obs()

    def _obs(self) -> np.ndarray:
        self.hist.append(self.obs_spec.build(self.robot, self.data, self.prev_a))
        return self.hist[max(0, len(self.hist) - 1 - self.lag_steps)]

    def step(self, a: np.ndarray):
        a = np.clip(np.asarray(a, dtype=float), -1.0, 1.0)
        self.data.ctrl[:] = self.stance + ACTION_SCALE * a
        t = self.k / CONTROL_HZ
        in_push = self.push_t <= t < self.push_t + PUSH_WINDOW_S
        self.data.xfrc_applied[self.robot.base_body_id] = self.push_force if in_push else 0.0
        for _ in range(self.steps_per_ctrl):
            mujoco.mj_step(self.model, self.data)
        self.k += 1
        R = self.data.xmat[self.robot.base_body_id].reshape(3, 3)
        tilt = float(np.degrees(np.arccos(np.clip(R[2, 2], -1.0, 1.0))))
        height = float(self.data.xpos[self.robot.base_body_id][2])
        fell = tilt > TILT_LIMIT_DEG or height < FALLEN_HEIGHT_M
        bad = not (np.all(np.isfinite(self.data.qpos)) and np.all(np.isfinite(self.data.qvel)))
        r = 1.0 - 0.5 * (tilt / TILT_LIMIT_DEG) ** 2 - 0.02 * float(np.mean(a ** 2))
        if fell or bad:
            r -= 5.0
        self.prev_a = a
        done = fell or bad
        timeout = self.k >= EPISODE_STEPS
        return self._obs(), r, done, timeout
