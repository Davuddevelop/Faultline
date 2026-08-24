"""The campaign builder must agree with the parser.

configure/configure.js ships its own copies of the axis names, the signal
names and the allowed key sets, because a browser cannot import Python. That
duplication is only safe if something fails when the two drift apart, so these
tests read the JavaScript and compare it against the real definitions.

The page also has to emit YAML that load() actually accepts — checked here by
generating the same document the page generates and loading it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from faultline.config import REDUCE_KEYS, REPORT_KEYS, SEARCH_KEYS, TOP_LEVEL, load
from faultline.reduce import SEVERITY_AXES
from faultline.runner import Trajectory
from faultline.search import METHODS

SITE = Path(__file__).resolve().parents[2]
JS = SITE / "configure" / "configure.js"

pytestmark = pytest.mark.skipif(
    not JS.exists(), reason="site not present (standalone harness checkout)"
)


@pytest.fixture(scope="module")
def js() -> str:
    return JS.read_text()


def _string_list(js: str, const: str) -> list[str]:
    """Pull `const NAME = ['a', 'b'];` out of the JavaScript."""
    m = re.search(rf"const {const}\s*=\s*\[(.*?)\]", js, re.S)
    assert m, f"{const} not found in configure.js"
    return re.findall(r"'([^']+)'", m.group(1))


def _axis_names(js: str) -> list[str]:
    m = re.search(r"const AXES\s*=\s*\[(.*?)\n\];", js, re.S)
    assert m, "AXES not found in configure.js"
    return re.findall(r"name:\s*'([^']+)'", m.group(1))


# ── the contract ──────────────────────────────────────────────────────


def test_the_page_offers_exactly_the_searchable_axes(js):
    """An axis the page offers but SearchSpace rejects is a config that looks
    right and fails on the first run."""
    assert _axis_names(js) == [a.field for a in SEVERITY_AXES]


def test_the_page_offers_exactly_the_signals_the_runner_computes(js):
    """A predicate against a signal Trajectory does not have raises KeyError
    mid-campaign, after the user has waited for it."""
    assert set(_string_list(js, "SIGNALS")) == {
        f for f in Trajectory.__dataclass_fields__ if f != "t"
    }


def test_the_page_offers_exactly_the_search_methods(js):
    assert set(_string_list(js, "METHODS")) == set(METHODS)


@pytest.mark.parametrize(
    "const,expected",
    [
        ("TOP_LEVEL", TOP_LEVEL),
        ("SEARCH_KEYS", SEARCH_KEYS),
        ("REDUCE_KEYS", REDUCE_KEYS),
        ("REPORT_KEYS", REPORT_KEYS),
    ],
)
def test_the_page_knows_the_same_keys_as_the_parser(js, const, expected):
    assert set(_string_list(js, const)) == set(expected)


def test_every_axis_the_page_shows_carries_a_unit(js):
    """Perturbation's whole contract is physical units, not normalised 0-1."""
    m = re.search(r"const AXES\s*=\s*\[(.*?)\n\];", js, re.S)
    assert len(re.findall(r"unit:\s*'([^']+)'", m.group(1))) == len(SEVERITY_AXES)


# ── the output ────────────────────────────────────────────────────────

# the document the page builds from its own defaults, byte for byte
DEFAULT_PAGE_OUTPUT = """\
# built at faultline/configure
# every key is read by faultline/config.py

robot: {model}
policy: stand
duration_s: 5

# three seeds, not one — a single seed
# would hide which component diverged
seeds:
  sampler: 41279
  sim: 0
  policy: 0

# the volume to search, in physical units
axes:
  push_impulse_ns: [0, 16]     # N·s
  slope_deg:       [0, 12]     # deg
  sensor_lag_ms:   [0, 50]     # ms

# what counts as a failure
# your rules, never a learned classifier
predicates:
  - name: tilt_limit
    signal: tilt_deg
    op: ">"
    threshold: 35
    grace_s: 0.3

search: {{method: cem, budget: 150}}
reduce: {{enabled: true, max: 10}}
report: {{out: deliverables/}}
"""


def test_the_pages_default_output_is_a_config_the_parser_accepts(tmp_path):
    """The quickstart cannot rot: what the page hands you must run."""
    model = SITE / "harness" / "models" / "quadruped.xml"
    path = tmp_path / "campaign.yaml"
    path.write_text(DEFAULT_PAGE_OUTPUT.format(model=model))

    campaign = load(path)

    assert set(campaign.space.bounds) == {
        "push_impulse_ns", "slope_deg", "sensor_lag_ms"
    }
    assert campaign.space.bounds["slope_deg"] == (0.0, 12.0)
    assert [p.name for p in campaign.spec.predicates] == ["tilt_limit"]
    assert campaign.spec.predicates[0].op == ">"
    assert campaign.spec.predicates[0].grace_s == 0.3
    assert campaign.method == "cem"
    assert campaign.budget == 150
    assert campaign.reduce_enabled is True
    assert campaign.spec.duration_s == 5.0
    assert campaign.spec.seeds.sampler == 41279

    # the baseline the page defaults to must actually load against this model
    assert campaign.policy() is not None


def test_the_quoted_op_survives_yaml(tmp_path):
    """`op: >` unquoted is a YAML block scalar, not the string '>'. The page
    quotes it; this is the test that says why."""
    doc = yaml.safe_load(DEFAULT_PAGE_OUTPUT.format(model="x.xml"))
    assert doc["predicates"][0]["op"] == ">"
