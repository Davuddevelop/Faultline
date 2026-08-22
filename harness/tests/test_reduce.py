"""What reduction claims, as tests.

The central claim is local minimality: no single axis of the reduced case can
be relaxed further without the failure disappearing. That is checked directly
rather than assumed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import mujoco
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import (  # noqa: E402
    Perturbation, Predicate, RunSpec, Seeds, StandPolicy,
    ReductionError, reduce_failure,
)
from faultline.reduce import SEVERITY_AXES, _model_friction, _violation  # noqa: E402

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")

PREDICATES = (
    Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),
    Predicate("fallen", "height_m", "<", 0.12, grace_s=0.3),
)

TOL = {a.field: a.tolerance for a in SEVERITY_AXES}


@pytest.fixture(scope="module")
def policy() -> StandPolicy:
    return StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])


def make_spec(**pert) -> RunSpec:
    return RunSpec(model_path=MODEL, policy_id="stand", predicates=PREDICATES,
                   duration_s=5.0, seeds=Seeds(sampler=1, sim=0, policy=0),
                   perturbation=Perturbation(**pert))


@pytest.fixture(scope="module")
def over_perturbed() -> RunSpec:
    """A failure caused by five things at once — the bad bug report."""
    return make_spec(push_impulse_ns=26.0, slope_deg=14.0, sensor_lag_ms=60.0,
                     payload_kg=1.2, torque_loss_pct=15.0)


@pytest.fixture(scope="module")
def reduced(over_perturbed, policy):
    return reduce_failure(over_perturbed, policy, budget=250)


def _nominal_of(field_: str, model_path: str) -> float:
    ax = next(a for a in SEVERITY_AXES if a.field == field_)
    return ax.nominal if ax.nominal is not None else _model_friction(model_path)


# ------------------------------------------------------------ the core claim

def test_relaxing_any_required_axis_below_the_minimum_stops_the_failure(reduced, policy):
    """This is the definition of locally minimal, checked rather than asserted.

    For every axis the reduced case still needs, nudging it one tolerance back
    toward nominal must make the failure go away. If it does not, the case was
    not minimal and the report would overstate how tight the condition is.
    """
    assert reduced.required, "nothing was required — the fixture is not exercising this"

    for f in reduced.required:
        value = getattr(reduced.minimal_spec.perturbation, f)
        nominal = _nominal_of(f, reduced.minimal_spec.model_path)
        step = TOL[f] * (1 if nominal > value else -1)
        relaxed = reduced.minimal_spec.with_perturbation(**{f: value + step})

        assert _violation(relaxed, policy, reduced.target_predicate) is None, (
            f"{f} relaxed from {value:.4g} to {value + step:.4g} still fails, "
            "so the reported case was not minimal"
        )


def test_the_minimal_case_still_fails(reduced, policy):
    assert _violation(reduced.minimal_spec, policy, reduced.target_predicate) is not None


def test_the_minimal_case_fires_the_same_predicate(reduced):
    assert reduced.minimal_violation.predicate == reduced.original_violation.predicate


# ------------------------------------------------------------- what it buys

def test_irrelevant_axes_are_eliminated(reduced):
    """The point of the feature: five perturbations in, a short list out."""
    assert len(reduced.eliminated) >= 2
    assert len(reduced.required) < 5
    for f in reduced.eliminated:
        assert getattr(reduced.minimal_spec.perturbation, f) in (0.0, None)


def test_reduction_costs_far_less_than_its_budget(reduced):
    assert 0 < reduced.evaluations <= reduced.budget
    assert reduced.locally_minimal


# ------------------------------------------------------------- determinism

def test_reduction_is_reproducible(over_perturbed, policy):
    a = reduce_failure(over_perturbed, policy, budget=250)
    b = reduce_failure(over_perturbed, policy, budget=250)
    assert a.minimal_spec.config_hash() == b.minimal_spec.config_hash()
    assert a.evaluations == b.evaluations


# ------------------------------------------------- what it refuses to do

def test_reducing_a_run_that_passed_raises(policy):
    with pytest.raises(ReductionError, match="did not fail"):
        reduce_failure(make_spec(push_impulse_ns=1.0), policy)


def test_targeting_a_predicate_that_never_fired_raises(over_perturbed, policy):
    with pytest.raises(ReductionError, match="did not fire"):
        reduce_failure(over_perturbed, policy, target_predicate="no_such_rule")


def test_a_named_target_predicate_is_the_one_preserved(over_perturbed, policy):
    result = reduce_failure(over_perturbed, policy, target_predicate="fallen", budget=250)
    assert result.target_predicate == "fallen"
    assert result.minimal_violation.predicate == "fallen"


def test_zero_budget_is_rejected(over_perturbed, policy):
    with pytest.raises(ValueError, match="budget"):
        reduce_failure(over_perturbed, policy, budget=0)


def test_budget_exhaustion_is_reported_and_not_called_minimal(over_perturbed, policy):
    """A truncated search must not be presented as a minimal case."""
    result = reduce_failure(over_perturbed, policy, budget=4)
    assert result.budget_exhausted
    assert not result.locally_minimal
    assert result.evaluations <= result.budget + 1     # the confirming probe


# --------------------------------------------------------- axis handling

def test_timing_and_direction_fields_are_never_reduced(policy):
    """push_time_s and the yaw fields are *when* and *which way*, not *how
    much*; shrinking them would change the case rather than minimise it."""
    spec = make_spec(push_impulse_ns=26.0, push_time_s=1.4, push_yaw_deg=35.0,
                     slope_deg=12.0, slope_yaw_deg=20.0)
    result = reduce_failure(spec, policy, budget=250)
    p = result.minimal_spec.perturbation
    assert p.push_time_s == 1.4
    assert p.push_yaw_deg == 35.0
    assert p.slope_yaw_deg == 20.0


def test_unset_friction_is_left_unset(reduced):
    assert reduced.minimal_spec.perturbation.friction_mu is None
    friction = next(a for a in reduced.axes if a.field == "friction_mu")
    assert friction.status == "untouched"


def test_a_perturbed_friction_is_reduced_toward_the_model_default(policy):
    """Friction's nominal is the model's own value, not zero, so relaxing it
    can mean moving either direction. The invariant is that it ends no further
    from the default than it started."""
    default = _model_friction(MODEL)
    spec = make_spec(friction_mu=1.5, push_impulse_ns=20.0)
    result = reduce_failure(spec, policy, budget=200)

    final = result.minimal_spec.perturbation.friction_mu
    if final is not None:
        assert abs(final - default) <= abs(1.5 - default) + TOL["friction_mu"]


# ------------------------------------------------------------------ record

def test_record_round_trips_and_names_the_original_run(reduced, over_perturbed, tmp_path):
    doc = json.loads(reduced.write(tmp_path / "reduction.json").read_text())

    assert doc["original_config_sha256"] == over_perturbed.config_hash()
    assert doc["minimal_config_sha256"] == reduced.minimal_spec.config_hash()
    assert doc["original_config_sha256"] != doc["minimal_config_sha256"]
    assert doc["target_predicate"] == reduced.target_predicate
    assert doc["locally_minimal"] is True
    assert doc["environment"]["mujoco"]
    assert {a["axis"] for a in doc["axes"]} == {a.field for a in SEVERITY_AXES}


def test_table_names_every_axis_and_its_status(reduced):
    text = reduced.table()
    for a in SEVERITY_AXES:
        assert a.field in text
    assert reduced.target_predicate in text
