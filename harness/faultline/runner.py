"""Deterministic execution of one RunSpec.

Determinism here means: same spec in, bit-identical trajectory out, on this
platform and this MuJoCo build. The runner enforces the parts it can (fixed
timestep from the model, single-threaded stepping, seeds passed through
explicitly) and records the parts it cannot (library version, platform) so a
divergence can be attributed rather than argued about.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

import mujoco
import numpy as np

from .policies import Policy
from .spec import RunSpec

GRAVITY = 9.81


@dataclass
class Trajectory:
    """Per-control-step signals. These are the only things predicates see."""

    t: np.ndarray
    tilt_deg: np.ndarray
    height_m: np.ndarray
    contact_force_n: np.ndarray
    joint_vel_rads: np.ndarray

    def signal(self, name: str) -> np.ndarray:
        try:
            return getattr(self, name)
        except AttributeError as exc:
            raise KeyError(
                f"unknown signal {name!r}; available: tilt_deg, height_m, "
                f"contact_force_n, joint_vel_rads"
            ) from exc

    def digest(self) -> str:
        """Hash of the trajectory, for proving a replay matched bit for bit."""
        import hashlib

        h = hashlib.sha256()
        for arr in (self.t, self.tilt_deg, self.height_m,
                    self.contact_force_n, self.joint_vel_rads):
            h.update(np.ascontiguousarray(arr, dtype=np.float64).tobytes())
        return h.hexdigest()


def sim_environment() -> dict[str, str]:
    """Recorded with every run: a replay that differs across these is expected
    to differ, and saying so up front is cheaper than discovering it later."""
    return {
        "mujoco": mujoco.__version__,
        "numpy": np.__version__,
        "python": platform.python_version(),
        "platform": f"{platform.system()}-{platform.machine()}",
    }


def _apply_perturbation(model: mujoco.MjModel, spec: RunSpec) -> None:
    """Everything that changes the world before the first step."""
    p = spec.perturbation

    if p.friction_mu is not None:
        if p.friction_mu <= 0:
            raise ValueError("friction_mu must be positive")
        # sliding friction only; torsional and rolling keep the model's values
        model.geom_friction[:, 0] = p.friction_mu

    # Slope is applied by rotating gravity rather than tilting the floor: the
    # contact geometry stays identical, so the only thing that varies between
    # runs is the quantity under test.
    if p.slope_deg:
        a = np.radians(p.slope_deg)
        yaw = np.radians(p.slope_yaw_deg)
        model.opt.gravity[:] = GRAVITY * np.array(
            [-np.sin(a) * np.cos(yaw), -np.sin(a) * np.sin(yaw), -np.cos(a)]
        )

    if p.torque_loss_pct:
        if not 0 <= p.torque_loss_pct < 100:
            raise ValueError("torque_loss_pct must be in [0, 100)")
        model.actuator_forcerange *= 1.0 - p.torque_loss_pct / 100.0
        model.actuator_gainprm[:, 0] *= 1.0 - p.torque_loss_pct / 100.0

    if p.payload_kg:
        torso = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
        if torso < 0:
            raise ValueError("payload requested but the model has no body named 'torso'")
        m0 = float(model.body_mass[torso])
        m1 = m0 + p.payload_kg
        # shift the centre of mass toward the payload
        com = model.body_ipos[torso].copy()
        com[0] = (com[0] * m0 + p.payload_offset_m * p.payload_kg) / m1
        model.body_ipos[torso] = com
        model.body_mass[torso] = m1
        model.body_inertia[torso] *= m1 / m0


def _torso_signals(model: mujoco.MjModel, data: mujoco.MjData,
                   torso_id: int) -> tuple[float, float, float]:
    R = data.xmat[torso_id].reshape(3, 3)
    # angle between the torso's own up axis and world up
    tilt = float(np.degrees(np.arccos(np.clip(R[2, 2], -1.0, 1.0))))
    height = float(data.xpos[torso_id][2])
    # external contact force magnitude on the torso; feet are excluded by
    # construction because we only read the torso body
    force = float(np.linalg.norm(data.cfrc_ext[torso_id][3:6]))
    return tilt, height, force


def run(spec: RunSpec, policy: Policy) -> Trajectory:
    """Execute one run. No search, no retries, no hidden state."""
    model = mujoco.MjModel.from_xml_path(spec.model_path)
    _apply_perturbation(model, spec)

    data = mujoco.MjData(model)
    if model.nkey > 0:
        mujoco.mj_resetDataKeyframe(model, data, 0)
    else:
        mujoco.mj_resetData(model, data)

    policy.reset(spec.seeds.policy)

    torso_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso")
    if torso_id < 0:
        raise ValueError("model has no body named 'torso'")

    dt = model.opt.timestep
    steps_per_ctrl = max(1, round((1.0 / spec.control_hz) / dt))
    n_ctrl = int(spec.duration_s * spec.control_hz)

    # Sensor lag is a ring of past observations; the policy sees a stale one.
    lag_steps = max(0, round((spec.perturbation.sensor_lag_ms / 1000.0) * spec.control_hz))
    obs_history: list[np.ndarray] = []

    p = spec.perturbation
    push_force = np.zeros(6)
    push_window = 0.05  # s; impulse is spread over this to stay solver-stable
    if p.push_impulse_ns:
        yaw = np.radians(p.push_yaw_deg)
        mag = p.push_impulse_ns / push_window
        push_force[:3] = [mag * np.cos(yaw), mag * np.sin(yaw), 0.0]

    t_arr = np.empty(n_ctrl)
    tilt_arr = np.empty(n_ctrl)
    height_arr = np.empty(n_ctrl)
    force_arr = np.empty(n_ctrl)
    jvel_arr = np.empty(n_ctrl)

    for k in range(n_ctrl):
        t = k / spec.control_hz

        obs = np.concatenate([data.qpos, data.qvel])
        obs_history.append(obs)
        seen = obs_history[max(0, len(obs_history) - 1 - lag_steps)]

        data.ctrl[:] = policy.act(seen, t)

        in_push = p.push_impulse_ns and (p.push_time_s <= t < p.push_time_s + push_window)
        data.xfrc_applied[torso_id] = push_force if in_push else 0.0

        for _ in range(steps_per_ctrl):
            mujoco.mj_step(model, data)

        mujoco.mj_rnePostConstraint(model, data)   # populates cfrc_ext
        tilt, height, force = _torso_signals(model, data, torso_id)
        t_arr[k] = t
        tilt_arr[k] = tilt
        height_arr[k] = height
        force_arr[k] = force
        jvel_arr[k] = float(np.abs(data.qvel[6:]).max()) if data.qvel.size > 6 else 0.0

    return Trajectory(t_arr, tilt_arr, height_arr, force_arr, jvel_arr)
