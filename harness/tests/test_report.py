"""What the deliverables claim, as tests.

The load-bearing part is the mode signature. If grouping were arbitrary, an
engineering report saying "three failure modes" would be a decorative number.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import mujoco
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import (  # noqa: E402
    Predicate, RunSpec, SearchSpace, Seeds, StandPolicy, build_report,
    cem_search, engineering_report, measure_coverage, random_search,
    safety_appendix, write_deliverables,
)

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")

SPACE = SearchSpace({
    "push_impulse_ns": (0, 9), "slope_deg": (0, 10), "sensor_lag_ms": (0, 60),
    "torque_loss_pct": (0, 15), "payload_kg": (0, 2.0), "payload_offset_m": (0, 0.06),
})

PREDICATES = (
    Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),
    Predicate("fallen", "height_m", "<", 0.12, grace_s=0.3),
)


@pytest.fixture(scope="module")
def policy() -> StandPolicy:
    return StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])


@pytest.fixture(scope="module")
def spec() -> RunSpec:
    return RunSpec(model_path=MODEL, policy_id="stand", duration_s=3.0,
                   seeds=Seeds(sampler=7, sim=0, policy=0), predicates=PREDICATES)


@pytest.fixture(scope="module")
def campaign(spec, policy):
    return cem_search(spec, policy, SPACE, budget=48, seed=0)


@pytest.fixture(scope="module")
def report(campaign, spec, policy):
    return build_report(campaign, spec, policy, max_reduce=5)


# ------------------------------------------------------------------- modes

def test_modes_are_grouped_by_what_the_failure_actually_needs(report):
    """Two failures share a mode when they reduce to the same required axes —
    an explainable signature, not a learned one."""
    assert report.modes, "the fixture campaign found no failures"
    signatures = [(m.predicate, m.required) for m in report.modes]
    assert len(signatures) == len(set(signatures)), "the same mode appears twice"


def test_every_reduced_failure_lands_in_exactly_one_mode(report):
    assert sum(len(m.members) for m in report.modes) == report.reduced_count


def test_each_mode_carries_a_locally_minimal_exemplar(report):
    for m in report.modes:
        assert m.exemplar.minimal_violation.predicate == m.predicate
        assert tuple(sorted(m.exemplar.required)) == m.required


def test_mode_region_covers_its_members(report):
    for m in report.modes:
        region = m.region(SPACE)
        for axis, r in region.items():
            vals = [x.perturbation[axis] for x in m.members]
            assert r["min"] == pytest.approx(min(vals), abs=1e-3)
            assert r["max"] == pytest.approx(max(vals), abs=1e-3)


def test_modes_are_ordered_by_how_common_they_are(report):
    counts = [len(m.members) for m in report.modes]
    assert counts == sorted(counts, reverse=True)


def test_the_reduction_cap_is_respected_and_reported(campaign, spec, policy):
    report = build_report(campaign, spec, policy, max_reduce=2)
    assert report.reduced_count == 2
    assert report.failures_total == len(campaign.failures)
    assert report.failures_total >= report.reduced_count


def test_only_the_most_severe_failures_are_reduced(campaign, spec, policy):
    report = build_report(campaign, spec, policy, max_reduce=3)
    chosen = [m.severity for mode in report.modes for m in mode.members]
    everything = sorted((s.severity for s in campaign.failures), reverse=True)
    assert sorted(chosen, reverse=True) == everything[:3]


# ---------------------------------------------------------------- coverage

def test_coverage_never_claims_more_than_was_sampled(campaign):
    cov = measure_coverage(campaign, bins=4)
    assert cov.cells_total == 4 ** campaign.space.dims
    assert 0 < cov.cells_visited <= min(campaign.budget, cov.cells_total)
    assert 0 < cov.fraction <= 1


def test_coverage_is_honest_about_a_high_dimensional_space(campaign):
    """Six axes at four bins is 4096 cells; a few dozen samples cannot fill it,
    and the number must show that rather than flatter the campaign."""
    cov = measure_coverage(campaign, bins=4)
    assert cov.fraction < 0.05


def test_sampled_range_sits_inside_the_declared_range(campaign):
    cov = measure_coverage(campaign)
    for axis, a in cov.per_axis.items():
        assert a["declared_min"] <= a["sampled_min"]
        assert a["sampled_max"] <= a["declared_max"]


# ----------------------------------------------------------- the documents

def test_engineering_report_names_every_mode_and_its_minimal_case(report):
    text = engineering_report(report)
    for m in report.modes:
        assert m.label in text
        for axis in m.required:
            assert axis in text
    assert "cannot show their absence" in text
    assert str(report.failures_total) in text


def test_safety_appendix_documents_every_predicate_and_the_space(report, spec):
    text = safety_appendix(report)
    for p in spec.predicates:
        assert f"`{p.name}`" in text
        assert str(p.threshold) in text
    for axis in SPACE.axes:
        assert f"`{axis}`" in text
    assert report.campaign.base_config_sha256 in text
    assert "does not assert conformity" in text
    assert "sampled the declared volume; it did not sweep it" in text


@pytest.mark.parametrize("phrase", [
    "demonstrates safety", "guarantees", "certifies", "is compliant",
    "proves the policy", "no failures exist", "verified safe",
])
def test_no_document_makes_an_affirmative_safety_claim(report, phrase):
    """A denial like "no claim is made that the policy is safe" is fine and
    wanted; what must never appear is the affirmative form."""
    for text in (engineering_report(report), safety_appendix(report)):
        assert phrase not in text.lower()


def test_both_documents_state_their_own_limits(report):
    assert "cannot show their absence" in engineering_report(report)
    appendix = safety_appendix(report)
    assert "does not assert conformity" in appendix
    assert "not evidence of safety" in appendix


def test_a_campaign_with_no_failures_still_produces_a_report(spec, policy):
    quiet = random_search(spec, policy, SearchSpace({"push_impulse_ns": (0, 0.4)}),
                          budget=6, seed=0)
    report = build_report(quiet, spec, policy, max_reduce=3)
    assert report.modes == []
    assert "No violations were found" in engineering_report(report)


def test_bad_reduction_cap_is_rejected(campaign, spec, policy):
    with pytest.raises(ValueError, match="max_reduce"):
        build_report(campaign, spec, policy, max_reduce=0)


# ------------------------------------------------------------------ archive

def test_archive_holds_one_manifest_line_per_run_with_its_provenance(report, policy, tmp_path):
    out = write_deliverables(report, policy, tmp_path / "deliverables")

    lines = (out / "archive" / "manifest.jsonl").read_text().strip().splitlines()
    assert len(lines) == report.campaign.budget

    first = json.loads(lines[0])
    assert len(first["config_sha256"]) == 64
    assert len(first["model_sha256"]) == 64
    assert first["seeds"] == {"sampler": 7, "sim": 0, "policy": 0}
    assert first["verdict"] in {"pass", "fail"}


def test_archive_writes_a_trajectory_trace_per_mode(report, policy, tmp_path):
    out = write_deliverables(report, policy, tmp_path / "deliverables")
    traces = sorted((out / "archive" / "traces").glob("*.csv"))
    assert len(traces) == len(report.modes)

    head, *rows = traces[0].read_text().strip().splitlines()
    assert head == "t,tilt_deg,height_m,contact_force_n,joint_vel_rads"
    assert len(rows) > 10
    assert len(rows[0].split(",")) == 5


def test_all_three_deliverables_are_written(report, policy, tmp_path):
    out = write_deliverables(report, policy, tmp_path / "deliverables")
    assert (out / "engineering-report.md").stat().st_size > 200
    assert (out / "safety-appendix.md").stat().st_size > 200
    assert (out / "archive" / "campaign.json").exists()
    assert (out / "archive" / "report.json").exists()


def test_report_json_round_trips(report, policy, tmp_path):
    out = write_deliverables(report, policy, tmp_path / "deliverables")
    doc = json.loads((out / "archive" / "report.json").read_text())
    assert doc["failures_reduced"] == report.reduced_count
    assert len(doc["modes"]) == len(report.modes)
    assert doc["coverage"]["cells_total"] == 4 ** SPACE.dims
    assert doc["space"] == SPACE.as_dict()
