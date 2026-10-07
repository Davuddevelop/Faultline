"""The Teeter site must say only what the harness and the record support.

teeter/index.html is filled by tools/build_teeter_site.py from the published
campaign record. Earlier pages in this repo drifted from the implementation
(ten axes when there were seven, predicate forms the runner cannot express),
so these tests read the built page and hold it to the code:

- the config sample is one load() accepts, and its axes, rules and budget are
  the record's;
- the axis table and the signal list are exactly what the harness has;
- every derived value on the page is what the record gives today, so a page
  left unbuilt after the record changes fails here rather than in public.
"""

from __future__ import annotations

import html
import importlib.util
import json
import re
from pathlib import Path

import pytest

from faultline.config import load
from faultline.runner import Trajectory
from faultline.space import _AXIS_BY_NAME

SITE = Path(__file__).resolve().parents[2]
PAGE = SITE / "teeter" / "index.html"
BUILDER = SITE / "tools" / "build_teeter_site.py"

pytestmark = pytest.mark.skipif(
    not (PAGE.exists() and BUILDER.exists()), reason="site not present (standalone harness checkout)"
)

WORDS = {4: "four", 7: "Seven"}


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text()


@pytest.fixture(scope="module")
def record() -> dict:
    return json.loads((SITE / "assets" / "data" / "campaign.json").read_text())


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def _builder():
    spec = importlib.util.spec_from_file_location("build_teeter_site", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── the config sample ─────────────────────────────────────────────────


def test_the_config_sample_is_one_the_parser_accepts(page, record, tmp_path):
    """The page calls it a reconstruction of the published campaign. It has to
    load, and the parts it says came from the record have to be the record's."""
    m = re.search(r"<!-- gen:yaml -->(.*?)<!-- /gen:yaml -->", page, re.S)
    assert m, "the page has no generated config sample"
    model = SITE / "harness" / "models" / "quadruped.xml"
    doc = re.sub(r"^robot: .*$", f"robot: {model}", _text(m.group(1)), flags=re.M)
    path = tmp_path / "campaign.yaml"
    path.write_text(doc)

    campaign = load(path)

    assert campaign.space.bounds == {k: (float(lo), float(hi)) for k, (lo, hi) in record["space"].items()}
    assert [(p.name, p.signal, p.op, p.threshold) for p in campaign.spec.predicates] == [
        (p["name"], p["signal"], p["op"], p["threshold"]) for p in record["report"]["predicates"]
    ]
    assert campaign.method == "cem"
    assert campaign.budget == record["budget"]
    assert campaign.reduce_max == record["report"]["reduced"]
    assert campaign.policy() is not None


# ── the contract ──────────────────────────────────────────────────────


def test_the_axis_table_lists_exactly_the_searchable_axes(page):
    table = re.search(r'<table class="spec">(.*?)</table>', page, re.S).group(1)
    fields = re.findall(r'<td class="mono">([a-z_]+)</td>', table)
    assert sorted(fields) == sorted(_AXIS_BY_NAME)
    assert f"{WORDS[len(_AXIS_BY_NAME)]}\n        axes can be searched today" in page


def test_the_rule_section_names_exactly_the_signals_the_runner_computes(page):
    signals = [f for f in Trajectory.__dataclass_fields__ if f != "t"]
    m = re.search(rf"Predicates see {WORDS[len(signals)]} signals and nothing else:(.*?)</p>", page, re.S)
    assert m, "the signal count in the prose no longer matches the runner"
    assert re.findall(r"<code>(\w+)</code>", m.group(1)) == signals


# ── the numbers ───────────────────────────────────────────────────────


def test_every_derived_value_is_the_records(page, record):
    sim = json.loads((SITE / "media" / "sim.json").read_text())
    want = _builder().site_values(record, sim)
    found = re.findall(r'\bdata-v="([\w.]+)"[^>]*>([^<]*)<', page)
    assert found, "no derived values on the page"
    stale = {k: (v, str(want[k])) for k, v in found if html.unescape(v) != str(want[k])}
    assert not stale, f"page is stale; rebuild with tools/build_teeter_site.py: {stale}"


def test_the_invented_address_is_flagged_beside_it(page):
    contact = re.search(r'<section class="contact".*?</section>', page, re.S).group(0)
    assert "hello@teeter.dev" in contact
    assert "That address is a placeholder" in contact
