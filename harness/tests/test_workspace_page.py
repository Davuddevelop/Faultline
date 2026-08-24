"""The workspace hands people a config. It has to be one the parser accepts.

app/app.js builds a campaign.yaml from the onboarding answers, choosing axes
and predicates per robot type. Those choices are made in JavaScript, so nothing
stops them drifting away from SEVERITY_AXES and the signals Trajectory
computes — except this.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from faultline.reduce import SEVERITY_AXES
from faultline.runner import Trajectory
from faultline.spec import Predicate

SITE = Path(__file__).resolve().parents[2]
JS = SITE / "app" / "app.js"

pytestmark = pytest.mark.skipif(
    not JS.exists(), reason="site not present (standalone harness checkout)"
)

AXIS_NAMES = {a.field for a in SEVERITY_AXES}
SIGNALS = {f for f in Trajectory.__dataclass_fields__ if f != "t"}


@pytest.fixture(scope="module")
def presets() -> dict[str, dict]:
    """Pull the per-robot axes and predicates out of the ROBOTS table."""
    js = JS.read_text()
    block = re.search(r"const ROBOTS = \{(.*?)\n\};", js, re.S)
    assert block, "ROBOTS table not found in app.js"

    out: dict[str, dict] = {}
    for m in re.finditer(
        r"(\w+):\s*\{\s*label:.*?axes:\s*\[(.*?)\],\s*preds:\s*\[(.*?)\],\s*why:",
        block.group(1), re.S
    ):
        name, axes_src, preds_src = m.groups()
        axes = [(a, float(lo), float(hi)) for a, lo, hi in
                re.findall(r"\['(\w+)',\s*([-\d.]+),\s*([-\d.]+)\]", axes_src)]
        preds = [(n, s, o, float(t)) for n, s, o, t in
                 re.findall(r"\['(\w+)',\s*'(\w+)',\s*'([<>])',\s*([-\d.]+)\]", preds_src)]
        out[name] = {"axes": axes, "preds": preds}
    assert out, "no robot presets parsed"
    return out


def test_every_preset_was_parsed(presets):
    assert set(presets) == {"quadruped", "humanoid", "arm", "mobile"}


@pytest.mark.parametrize("robot", ["quadruped", "humanoid", "arm", "mobile"])
def test_preset_axes_are_all_searchable(presets, robot):
    """An axis SearchSpace rejects makes the handed-out config fail on run 1."""
    names = [a for a, _, _ in presets[robot]["axes"]]
    assert names, f"{robot} declares no axes"
    unknown = set(names) - AXIS_NAMES
    assert not unknown, f"{robot} offers unsearchable axes: {sorted(unknown)}"


@pytest.mark.parametrize("robot", ["quadruped", "humanoid", "arm", "mobile"])
def test_preset_ranges_are_non_empty(presets, robot):
    for name, lo, hi in presets[robot]["axes"]:
        assert lo < hi, f"{robot}.{name} has an empty range [{lo}, {hi}]"


@pytest.mark.parametrize("robot", ["quadruped", "humanoid", "arm", "mobile"])
def test_preset_predicates_are_constructible(presets, robot):
    """Predicate validates op and grace_s itself, so build the real thing."""
    preds = presets[robot]["preds"]
    assert preds, f"{robot} declares no predicates"
    for name, signal, op, threshold in preds:
        assert signal in SIGNALS, f"{robot}.{name} reads unknown signal {signal!r}"
        Predicate(name=name, signal=signal, op=op, threshold=threshold)


@pytest.mark.parametrize("robot", ["quadruped", "humanoid", "arm", "mobile"])
def test_preset_serialises_to_loadable_yaml(presets, robot):
    """The document the page emits must survive a YAML round trip with the
    quoted operator intact — bare `op: >` is a block scalar, not '>'."""
    p = presets[robot]
    doc = "\n".join(
        ["robot: r.xml", "policy: stand", "duration_s: 5", "", "axes:"]
        + [f"  {n}: [{lo}, {hi}]" for n, lo, hi in p["axes"]]
        + ["", "predicates:"]
        + [f'  - {{name: {n}, signal: {s}, op: "{o}", threshold: {t}}}'
           for n, s, o, t in p["preds"]]
    )
    loaded = yaml.safe_load(doc)
    assert set(loaded["axes"]) == {n for n, _, _ in p["axes"]}
    for got, (n, s, o, t) in zip(loaded["predicates"], p["preds"]):
        assert got["op"] == o and got["signal"] == s


def test_the_arm_preset_does_not_watch_tilt(presets):
    """A fixed base cannot topple. Shipping tilt_deg to an arm customer would
    be a rule that can never fire, which is worse than no rule."""
    signals = {s for _, s, _, _ in presets["arm"]["preds"]}
    assert "tilt_deg" not in signals
