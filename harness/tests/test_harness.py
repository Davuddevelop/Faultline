"""The claims this harness makes, as tests.

The product claim is that any recorded run can be re-run by someone who does
not trust us. These tests are that claim, checked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import mujoco
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import (  # noqa: E402
    JitterPolicy, Perturbation, Predicate, RunSpec, Seeds, StandPolicy,
    evaluate, execute, replay, run,
)

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")

PREDICATES = (
    Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),
    Predicate("fallen", "height_m", "<", 0.12, grace_s=0.3),
)


@pytest.fixture(scope="module")
def nominal_ctrl() -> np.ndarray:
    return mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0].copy()


@pytest.fixture
def stand(nominal_ctrl) -> StandPolicy:
    return StandPolicy(nominal_ctrl)


def spec(**kw) -> RunSpec:
    base = dict(model_path=MODEL, policy_id="x", predicates=PREDICATES, duration_s=3.0)
    base.update(kw)
    return RunSpec(**base)


# ---------------------------------------------------------------- determinism

def test_same_spec_gives_bit_identical_trajectory(stand):
    s = spec(policy_id=stand.id, perturbation=Perturbation(push_impulse_ns=12.0))
    assert run(s, stand).digest() == run(s, stand).digest()


def test_stochastic_policy_is_reproducible_from_its_seed(nominal_ctrl):
    s = spec(policy_id="jitter", seeds=Seeds(policy=7))
    assert run(s, JitterPolicy(nominal_ctrl)).digest() == run(s, JitterPolicy(nominal_ctrl)).digest()


def test_policy_seed_actually_reaches_the_policy(nominal_ctrl):
    """If the seed were ignored, these would match and the seed field would be
    decoration."""
    a = run(spec(policy_id="jitter", seeds=Seeds(policy=1)), JitterPolicy(nominal_ctrl))
    b = run(spec(policy_id="jitter", seeds=Seeds(policy=2)), JitterPolicy(nominal_ctrl))
    assert a.digest() != b.digest()


def test_perturbation_changes_the_outcome(stand):
    quiet = run(spec(policy_id=stand.id), stand)
    shoved = run(spec(policy_id=stand.id,
                      perturbation=Perturbation(push_impulse_ns=20.0)), stand)
    assert quiet.digest() != shoved.digest()
    assert shoved.tilt_deg.max() > quiet.tilt_deg.max()


# --------------------------------------------------------------- provenance

def test_config_hash_ignores_field_ordering(stand):
    a = RunSpec(model_path=MODEL, policy_id="p", predicates=PREDICATES,
                perturbation=Perturbation(slope_deg=5.0, friction_mu=0.8))
    b = RunSpec(predicates=PREDICATES, policy_id="p", model_path=MODEL,
                perturbation=Perturbation(friction_mu=0.8, slope_deg=5.0))
    assert a.config_hash() == b.config_hash()


def test_config_hash_separates_different_perturbations():
    a = RunSpec(model_path=MODEL, policy_id="p").with_perturbation(slope_deg=5.0)
    b = RunSpec(model_path=MODEL, policy_id="p").with_perturbation(slope_deg=5.001)
    assert a.config_hash() != b.config_hash()


# ---------------------------------------------------------------- predicates

def test_violation_reports_which_rule_and_when(stand):
    rec, _ = execute(spec(policy_id=stand.id,
                          perturbation=Perturbation(push_impulse_ns=25.0)), stand)
    assert rec.failed
    v = rec.violations[0]
    assert v.predicate in {"tilt_limit", "fallen"}
    assert 1.0 <= v.first_t <= 3.0        # the push lands at t=1.0
    assert v.peak > v.threshold or v.op == "<"


def test_breach_then_recovery_still_counts(stand):
    """A trajectory that exceeds a limit and comes back has still exceeded it."""
    from faultline.runner import Trajectory

    t = np.linspace(0, 3, 100)
    tilt = np.where((t > 1) & (t < 1.5), 50.0, 5.0)     # breaches, then recovers
    traj = Trajectory(t, tilt, np.full(100, 0.2), np.zeros(100), np.zeros(100))

    hits = evaluate(traj, (Predicate("tilt", "tilt_deg", ">", 35.0),))
    assert len(hits) == 1 and hits[0].first_t == pytest.approx(1.0, abs=0.05)


def test_grace_period_suppresses_startup_transients():
    from faultline.runner import Trajectory

    t = np.linspace(0, 3, 100)
    tilt = np.where(t < 0.2, 90.0, 1.0)                 # settles immediately
    traj = Trajectory(t, tilt, np.full(100, 0.2), np.zeros(100), np.zeros(100))

    assert evaluate(traj, (Predicate("tilt", "tilt_deg", ">", 35.0),))
    assert not evaluate(traj, (Predicate("tilt", "tilt_deg", ">", 35.0, grace_s=0.5),))


def test_unknown_signal_is_rejected_loudly(stand):
    traj = run(spec(policy_id=stand.id, duration_s=0.5), stand)
    with pytest.raises(KeyError, match="unknown signal"):
        evaluate(traj, (Predicate("bogus", "vibes", ">", 1.0),))


def test_bad_operator_is_rejected_at_construction():
    with pytest.raises(ValueError, match="must be"):
        Predicate("x", "tilt_deg", ">=", 1.0)


# -------------------------------------------------------------------- replay

def test_recorded_run_replays_to_the_same_digest(stand, tmp_path):
    """The whole product claim, in one test."""
    s = spec(policy_id=stand.id, perturbation=Perturbation(push_impulse_ns=18.0,
                                                           slope_deg=6.0,
                                                           sensor_lag_ms=40.0))
    rec, _ = execute(s, stand)
    path = rec.write(tmp_path / "run.json")

    result = replay(path, stand)
    assert result.matched, result.notes
    assert result.model_matched and result.environment_matched
    assert result.notes == []


def test_replay_flags_a_substituted_policy(stand, nominal_ctrl, tmp_path):
    rec, _ = execute(spec(policy_id=stand.id), stand)
    path = rec.write(tmp_path / "run.json")

    result = replay(path, JitterPolicy(nominal_ctrl))
    assert not result.matched
    assert any("policy differs" in n for n in result.notes)


def test_record_round_trips_through_json(stand, tmp_path):
    s = spec(policy_id=stand.id, perturbation=Perturbation(friction_mu=0.4, slope_deg=3.0))
    rec, _ = execute(s, stand)
    doc = json.loads(rec.write(tmp_path / "r.json").read_text())

    assert RunSpec.from_dict(doc["spec"]).config_hash() == s.config_hash()
    assert doc["verdict"] in {"pass", "fail"}
    assert doc["environment"]["mujoco"]
    assert len(doc["trajectory_sha256"]) == 64


# ------------------------------------------------------------ input validation

@pytest.mark.parametrize("bad", [
    dict(friction_mu=0.0),
    dict(torque_loss_pct=100.0),
    dict(torque_loss_pct=-1.0),
])
def test_physically_impossible_perturbations_are_rejected(stand, bad):
    with pytest.raises(ValueError):
        run(spec(policy_id=stand.id).with_perturbation(**bad), stand)


def test_contact_force_signal_is_actually_populated(stand):
    """Regression: cfrc_ext is only filled by mj_rnePostConstraint, which
    mj_step does not call on its own. Without it this signal was identically
    zero and any predicate on it silently never fired — the failure mode where
    a campaign reports no violations because the rule could not fire."""
    _, traj = execute(spec(policy_id=stand.id, duration_s=4.0,
                           perturbation=Perturbation(push_impulse_ns=25.0)), stand)
    assert traj.contact_force_n.max() > 1.0
