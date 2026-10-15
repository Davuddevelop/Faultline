"""Loading somebody else's robot, and telling the policy what it sees.

These cover the assumptions the harness used to make silently: a body named
`torso`, a floating base, and a fixed [qpos, qvel] observation. Each was fine
for our stand-in quadruped and wrong for everything else.
"""

from __future__ import annotations

import numpy as np
import mujoco
import pytest

from faultline.model import ModelError, load
from faultline.observe import ObservationError, ObservationSpec, Term
from faultline.runner import SimulationDiverged, run
from faultline.spec import Predicate, RunSpec, Seeds

ARM = """<mujoco model="arm3">
  <worldbody><body name="base_link">
    <geom type="box" size="0.05 0.05 0.05"/>
    <body name="l1"><joint name="shoulder" axis="0 0 1"/><geom type="capsule" fromto="0 0 0 0 0 .3" size=".03"/>
      <body name="l2" pos="0 0 .3"><joint name="elbow" axis="0 1 0"/><geom type="capsule" fromto="0 0 0 0 0 .3" size=".03"/>
      </body></body></body></worldbody>
  <actuator><motor name="a1" joint="shoulder"/><motor name="a2" joint="elbow"/></actuator>
</mujoco>"""

NO_ACTUATOR = """<mujoco><worldbody><body name="b">
  <joint name="j" axis="0 0 1"/><geom type="box" size=".1 .1 .1"/>
</body></worldbody></mujoco>"""


@pytest.fixture
def arm(tmp_path):
    p = tmp_path / "arm.xml"
    p.write_text(ARM)
    return load(p)


@pytest.fixture
def quad():
    return load("models/quadruped.xml")


# ── model ingest ──────────────────────────────────────────────────────


def test_base_is_resolved_without_being_told(arm, quad):
    """The old runner required a body literally named 'torso'."""
    assert arm.base_body == "base_link" and not arm.free_base
    assert quad.base_body == "torso" and quad.free_base


def test_fixed_base_joints_are_not_offset_by_six(arm):
    """The old jvel read qvel[6:], which on a fixed base skips real joints.
    An arm's first joint lives at dof 0."""
    assert list(arm.dof_adr) == [0, 1]
    assert arm.n_joints == 2


def test_floating_base_joints_skip_the_free_joint(quad):
    assert quad.dof_adr[0] == 6 and quad.qpos_adr[0] == 7


def test_a_model_without_actuators_is_refused(tmp_path):
    p = tmp_path / "n.xml"
    p.write_text(NO_ACTUATOR)
    with pytest.raises(ModelError, match="no actuators"):
        load(p)


def test_a_missing_file_names_itself(tmp_path):
    with pytest.raises(ModelError, match="no such model file"):
        load(tmp_path / "absent.xml")


def test_a_wrong_base_name_lists_what_is_there(tmp_path):
    p = tmp_path / "arm.xml"
    p.write_text(ARM)
    with pytest.raises(ModelError, match="base_link"):
        load(p, base_body="torso")


# ── observation ───────────────────────────────────────────────────────


def test_declared_width_matches_what_is_built(quad):
    spec = ObservationSpec.default()
    d = mujoco.MjData(quad.model)
    mujoco.mj_resetDataKeyframe(quad.model, d, 0)
    mujoco.mj_forward(quad.model, d)
    obs = spec.build(quad, d, np.zeros(quad.n_actuators))
    assert obs.shape[0] == spec.size(quad)


@pytest.mark.parametrize("roll,expected", [
    (0, [0, 0, -1]), (90, [0, -1, 0]), (-90, [0, 1, 0]), (180, [0, 0, 1]),
])
def test_projected_gravity_tracks_orientation(quad, roll, expected):
    """The body-frame transform is the calculation most easily wrong, and a
    silent sign error would mislead every locomotion policy."""
    d = mujoco.MjData(quad.model)
    mujoco.mj_resetDataKeyframe(quad.model, d, 0)
    c, s = np.cos(np.radians(roll) / 2), np.sin(np.radians(roll) / 2)
    d.qpos[3:7] = [c, s, 0, 0]
    mujoco.mj_forward(quad.model, d)
    got = ObservationSpec((Term("projected_gravity"),)).build(
        quad, d, np.zeros(quad.n_actuators))
    assert np.allclose(got, expected, atol=1e-6)


def test_base_terms_are_refused_on_a_fixed_base(arm):
    """Feeding a policy zeros where it expects base motion is the quiet kind
    of wrong this harness exists to prevent."""
    with pytest.raises(ObservationError, match="floating base"):
        ObservationSpec((Term("base_ang_vel"),)).validate(arm)


def test_an_unknown_term_lists_the_real_ones():
    with pytest.raises(ObservationError, match="unknown observation term"):
        Term("base_velocity")


def test_a_mistyped_key_is_named():
    with pytest.raises(ObservationError, match="scal"):
        ObservationSpec.from_list([{"term": "joint_pos", "scal": 2}])


def test_the_layout_is_part_of_the_config_hash():
    """Change what the policy sees and it is a different experiment, so a
    replay against the old digest must not silently pass."""
    a = RunSpec(model_path="models/quadruped.xml", policy_id="p",
                observation=({"term": "joint_pos"},))
    b = RunSpec(model_path="models/quadruped.xml", policy_id="p",
                observation=({"term": "joint_vel"},))
    assert a.config_hash() != b.config_hash()


# ── divergence ────────────────────────────────────────────────────────


class Constant:
    def __init__(self, v, n=2): self.v, self.n = v, n
    def reset(self, seed): pass
    def act(self, obs, t): return np.full(self.n, self.v)


def _arm_spec(tmp_path):
    p = tmp_path / "arm.xml"
    p.write_text(ARM)
    return RunSpec(
        model_path=str(p), policy_id="p",
        predicates=(Predicate("speed", "joint_vel_rads", ">", 1.0),),
        seeds=Seeds(0, 0, 0), duration_s=2.0,
        observation=({"term": "joint_pos"},),
    )


@pytest.mark.parametrize("policy,why", [
    # the threshold is model-dependent; 1e8 diverges this two-link arm
    (Constant(1e8), "a control large enough to blow the solver up"),
    # At 1e12 MuJoCo raises BADCTRL and silently resets the control to zero,
    # so the run stays numerically perfect and would otherwise be recorded as
    # a clean pass while the policy's output never reached the robot.
    (Constant(1e12), "a control MuJoCo rejects and zeroes"),
    (Constant(float("nan")), "a non-finite action"),
    (Constant(0.0, n=5), "an action of the wrong width"),
])
def test_an_unusable_run_is_never_reported_as_a_policy_failure(tmp_path, policy, why):
    with pytest.raises(SimulationDiverged):
        run(_arm_spec(tmp_path), policy)


def test_a_usable_run_still_returns_a_trajectory(tmp_path):
    traj = run(_arm_spec(tmp_path), Constant(0.05))
    assert np.all(np.isfinite(traj.tilt_deg)) and traj.t.size > 10


def test_relative_joint_pos_is_offset_from_the_starting_pose(quad):
    """Regression: 'relative' subtracted qpos0, which is all zeros for this
    model, so a policy trained on joint_pos - default_pos (Isaac Lab,
    legged_gym) was fed absolute angles. At the keyframe the offsets are zero."""
    d = mujoco.MjData(quad.model)
    mujoco.mj_resetDataKeyframe(quad.model, d, 0)
    mujoco.mj_forward(quad.model, d)
    rel = ObservationSpec((Term("joint_pos", relative=True),)).build(quad, d, np.zeros(quad.n_actuators))
    absolute = ObservationSpec((Term("joint_pos"),)).build(quad, d, np.zeros(quad.n_actuators))
    assert np.allclose(rel, 0.0, atol=1e-12)
    assert np.allclose(absolute, quad.model.key_qpos[0][quad.qpos_adr])
    assert not np.allclose(absolute, 0.0), "the fixture must start away from qpos0 to test this"


CRATE_FIRST = """<mujoco>
  <worldbody>
    <body name="crate" pos="1 0 0.2"><freejoint/><geom type="box" size=".1 .1 .1"/></body>
    <body name="base" pos="0 0 0.5"><freejoint/><geom type="box" size=".2 .1 .05"/>
      <body name="leg"><joint name="hip" axis="0 1 0"/><geom type="capsule" fromto="0 0 0 0 0 -.3" size=".02"/></body>
    </body>
  </worldbody>
  <actuator><motor name="m" joint="hip"/></actuator>
</mujoco>"""


def test_base_terms_read_the_bases_own_free_joint(tmp_path):
    """A loose object declared before the robot takes qpos[0:7]. Reading the
    base's quaternion from there gave the crate's orientation to the policy."""
    p = tmp_path / "scene.xml"
    p.write_text(CRATE_FIRST)
    robot = load(p, base_body="base")
    assert robot.base_qpos_adr == 7 and robot.base_dof_adr == 6
    d = mujoco.MjData(robot.model)
    d.qpos[3:7] = [0.0, 1.0, 0.0, 0.0]                  # the crate, upside down
    d.qpos[10:14] = [1.0, 0.0, 0.0, 0.0]                # the robot, upright
    mujoco.mj_forward(robot.model, d)
    got = ObservationSpec((Term("base_quat"),)).build(robot, d, np.zeros(1))
    assert np.allclose(got, [1.0, 0.0, 0.0, 0.0])

    unnamed = load(p)
    assert unnamed.base_body == "crate"
    assert any("free joints" in n for n in unnamed.notes), "two free bodies must be called out"
