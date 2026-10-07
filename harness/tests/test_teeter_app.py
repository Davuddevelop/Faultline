"""The app prototype must show only what the harness and the record support.

teeter/app/ draws every "record" panel from teeter/app/js/record.js, which
tools/build_teeter_app.py writes by reading the harness's source as text (so it
runs without MuJoCo). These tests import the harness and hold that file to it:
the axes, signals, observation layout, robot and control rate are the code's,
and the file is what the builder would write today.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from faultline.model import load
from faultline.observe import ObservationSpec
from faultline.reduce import SEVERITY_AXES
from faultline.runner import Trajectory
from faultline.space import _AXIS_BY_NAME

ROOT = Path(__file__).resolve().parents[2]
RECORD_JS = ROOT / "teeter" / "app" / "js" / "record.js"
BUILDER = ROOT / "tools" / "build_teeter_app.py"
APP = ROOT / "teeter" / "app"

pytestmark = pytest.mark.skipif(
    not (RECORD_JS.exists() and BUILDER.exists()), reason="app prototype not present (standalone harness checkout)"
)


def _builder():
    spec = importlib.util.spec_from_file_location("build_teeter_app", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rec() -> dict:
    text = RECORD_JS.read_text()
    m = re.search(r"window\.TEETER_RECORD = (\{.*?\});\n", text, re.S)
    return json.loads(m.group(1))


def test_record_js_is_fresh():
    assert RECORD_JS.read_text() == _builder().build(), "run python3 tools/build_teeter_app.py"


def test_axes_are_the_harness_axes(rec):
    assert [a["name"] for a in rec["axes"]] == [a.field for a in SEVERITY_AXES]
    assert {a["name"] for a in rec["axes"]} == set(_AXIS_BY_NAME)
    for a in rec["axes"]:
        h = _AXIS_BY_NAME[a["name"]]
        assert (a["nominal"], a["tolerance"], a["unit"]) == (h.nominal, h.tolerance, h.unit)


def test_signals_are_the_trajectory_fields(rec):
    fields = [f for f in Trajectory.__dataclass_fields__ if f != "t"]
    assert rec["signals"] == fields


def test_robot_and_layout_are_what_the_harness_reads(rec):
    robot = load(ROOT / "harness" / "models" / "quadruped.xml")
    assert rec["robot"]["sha256"] == robot.source_sha256
    assert rec["robot"]["joints"] == list(robot.actuated_joints)
    assert len(rec["robot"]["actuators"]) == robot.n_actuators
    assert rec["robot"]["bodies"] == robot.model.nbody
    assert rec["robot"]["free_base"] == robot.base_body
    assert rec["robot"]["timestep"] == robot.model.opt.timestep
    spec = ObservationSpec.default()
    assert [t["kind"] for t in rec["layout"]] == [t.kind for t in spec.terms]
    assert rec["layout"][-1]["to"] == spec.size(robot)
    widths = [t["to"] - t["from"] for t in rec["layout"]]
    assert widths == [t.width(robot) for t in spec.terms]
    assert [t["scale"] for t in rec["layout"]] == [t.scale for t in spec.terms]


def test_example_data_never_claims_to_be_the_record():
    """The example file labels itself, and the app tags every panel."""
    ex = (APP / "js" / "example.js").read_text()
    assert "ILLUSTRATIVE" in ex
    app = (APP / "js" / "app.js").read_text().lower()
    # the only places these may appear are where the app says it does not claim them
    for denial in ("calls a policy safe", "does not show</p><ul><li>that the policy is safe"):
        app = app.replace(denial, "")
    for word in ("certified", "compliant", "validated", "verified safe", "is safe"):
        assert word not in app, word
