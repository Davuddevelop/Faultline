"""What search claims, as tests.

Note what is *not* here: any assertion that the directed method beats random.
At a 2.5% failure rate that outcome varies by seed, and encoding a superiority
claim as a passing test is exactly the overclaiming this product exists to
avoid. What is tested is the mechanism — that CEM concentrates — and the
invariants a customer's declared space depends on.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import mujoco
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import (  # noqa: E402
    Predicate, RunSpec, SearchSpace, Seeds, StandPolicy,
    cem_search, compare, random_search, reduce_failure,
)

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")

# The regime measured while planning: ~2.5% of uniform samples fail, so
# sample efficiency is a real question rather than a foregone conclusion.
TIGHT = {
    "push_impulse_ns": (0, 9), "slope_deg": (0, 10), "sensor_lag_ms": (0, 60),
    "torque_loss_pct": (0, 15), "payload_kg": (0, 2.0), "payload_offset_m": (0, 0.06),
}


@pytest.fixture(scope="module")
def policy() -> StandPolicy:
    return StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])


@pytest.fixture(scope="module")
def spec() -> RunSpec:
    return RunSpec(
        model_path=MODEL, policy_id="stand", duration_s=3.0,
        seeds=Seeds(sampler=0, sim=0, policy=0),
        predicates=(Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),),
    )


@pytest.fixture(scope="module")
def space() -> SearchSpace:
    return SearchSpace(TIGHT)


# ------------------------------------------------------------ space validity

def test_unknown_axis_is_rejected():
    with pytest.raises(ValueError, match="not a searchable axis"):
        SearchSpace({"wind_speed": (0, 10)})


def test_timing_fields_are_not_searchable():
    """push_time_s is *when*, not *how much* — it belongs on the base spec."""
    with pytest.raises(ValueError, match="not a searchable axis"):
        SearchSpace({"push_time_s": (0, 2)})


def test_inverted_bounds_are_rejected():
    with pytest.raises(ValueError, match="upper bound"):
        SearchSpace({"slope_deg": (10, 5)})


def test_empty_space_is_rejected():
    with pytest.raises(ValueError, match="at least one axis"):
        SearchSpace({})


# ------------------------------------------------------------- the invariant

@pytest.mark.parametrize("method", [random_search, cem_search])
def test_every_sample_lies_inside_the_declared_bounds(spec, policy, space, method):
    """The customer declared this volume; nothing may be run outside it."""
    result = method(spec, policy, space, budget=36, seed=3)
    for s in result.samples:
        for axis, value in s.perturbation.items():
            lo, hi = TIGHT[axis]
            assert lo <= value <= hi, f"{axis}={value} escaped [{lo}, {hi}]"


@pytest.mark.parametrize("method", [random_search, cem_search])
def test_budget_is_spent_exactly(spec, policy, space, method):
    for budget in (7, 20, 33):
        assert len(method(spec, policy, space, budget=budget, seed=1).samples) == budget


# -------------------------------------------------------------- determinism

@pytest.mark.parametrize("method", [random_search, cem_search])
def test_reproducible_from_its_seed(spec, policy, space, method):
    a = method(spec, policy, space, budget=24, seed=11)
    b = method(spec, policy, space, budget=24, seed=11)
    assert [s.perturbation for s in a.samples] == [s.perturbation for s in b.samples]
    assert [s.severity for s in a.samples] == [s.severity for s in b.samples]


@pytest.mark.parametrize("method", [random_search, cem_search])
def test_different_seeds_explore_differently(spec, policy, space, method):
    a = method(spec, policy, space, budget=24, seed=1)
    b = method(spec, policy, space, budget=24, seed=2)
    assert [s.perturbation for s in a.samples] != [s.perturbation for s in b.samples]


# ---------------------------------------------------------- the mechanism

def test_cem_concentrates_where_severity_is_higher(spec, policy, space):
    """The actual claim behind "a directed search". If later rounds are no
    more severe than the first, CEM is just an expensive random search."""
    result = cem_search(spec, policy, space, budget=60, seed=0, iterations=5)

    by_round: dict[int, list[float]] = {}
    for s in result.samples:
        by_round.setdefault(s.iteration, []).append(s.severity)
    assert len(by_round) >= 3, "not enough rounds to show concentration"

    first = statistics.mean(by_round[min(by_round)])
    last = statistics.mean(by_round[max(by_round)])
    assert last > first, f"severity did not climb: round means {by_round.keys()}"


def test_random_search_does_not_concentrate(spec, policy, space):
    """The control: uniform sampling has a single round and no adaptation."""
    result = random_search(spec, policy, space, budget=30, seed=0)
    assert {s.iteration for s in result.samples} == {0}


# ------------------------------------------------------------- bookkeeping

def test_first_failure_index_points_at_the_first_failing_sample(spec, policy, space):
    result = cem_search(spec, policy, space, budget=60, seed=0)
    idx = result.first_failure_index
    if idx is None:
        assert not result.failures
    else:
        assert result.samples[idx].failed
        assert all(not s.failed for s in result.samples[:idx])


def test_worst_sample_has_the_highest_severity(spec, policy, space):
    result = random_search(spec, policy, space, budget=24, seed=5)
    assert result.worst.severity == max(s.severity for s in result.samples)


def test_a_space_pinned_near_nominal_finds_nothing(spec, policy):
    quiet = SearchSpace({"push_impulse_ns": (0, 0.4), "slope_deg": (0, 0.4)})
    result = random_search(spec, policy, quiet, budget=20, seed=0)
    assert result.failures == []
    assert result.first_failure_index is None


# --------------------------------------------------------------- refusals

def test_a_spec_with_no_predicates_is_rejected(policy, space):
    bare = RunSpec(model_path=MODEL, policy_id="stand", duration_s=3.0)
    with pytest.raises(ValueError, match="no predicates"):
        random_search(bare, policy, space, budget=5)


def test_unknown_target_predicate_is_rejected(spec, policy, space):
    with pytest.raises(ValueError, match="not on this spec"):
        random_search(spec, policy, space, budget=5, target_predicate="nope")


@pytest.mark.parametrize("kw", [
    dict(budget=0), dict(budget=10, iterations=0), dict(budget=10, elite_frac=0.0),
    dict(budget=10, elite_frac=1.5),
])
def test_nonsense_parameters_are_rejected(spec, policy, space, kw):
    with pytest.raises(ValueError):
        cem_search(spec, policy, space, seed=0, **kw)


# ----------------------------------------------------------------- record

def test_campaign_record_round_trips(spec, policy, space, tmp_path):
    result = cem_search(spec, policy, space, budget=24, seed=0)
    doc = json.loads(result.write(tmp_path / "campaign.json").read_text())

    assert doc["method"] == "cem"
    assert doc["budget"] == 24 and len(doc["samples"]) == 24
    assert doc["base_config_sha256"] == spec.config_hash()
    assert doc["space"] == space.as_dict()
    assert doc["target_predicate"] == "tilt_limit"
    assert doc["environment"]["mujoco"]


def test_comparison_reports_every_seed_for_every_method(spec, policy, space):
    result = compare(spec, policy, space, budget=16, seeds=(0, 1), methods=("random", "cem"))
    assert set(result.campaigns) == {"random", "cem"}
    assert all(len(runs) == 2 for runs in result.campaigns.values())

    doc = result.as_dict()
    assert len(doc["methods"]["cem"]["failures_per_seed"]) == 2
    # it must not imply more confidence than two seeds support
    assert "not a significance test" in result.summary()


def test_unknown_method_is_rejected(spec, policy, space):
    with pytest.raises(ValueError, match="unknown method"):
        compare(spec, policy, space, budget=5, seeds=(0,), methods=("psychic",))


# ------------------------------------------------------------- integration

def test_a_failure_found_by_search_can_be_reduced(spec, policy, space):
    """01 -> 03 -> 05 end to end: search finds a failing point, reduction
    minimises it."""
    found = cem_search(spec, policy, space, budget=60, seed=0)
    assert found.failures, "the fixture space stopped producing failures"

    worst = max(found.failures, key=lambda s: s.severity)
    failing_spec = spec.with_perturbation(**worst.perturbation)

    reduced = reduce_failure(failing_spec, policy, budget=120)
    assert reduced.minimal_violation.predicate == "tilt_limit"
    assert reduced.required, "reduction eliminated every axis, which cannot be right"
