"""tools/publish_campaign.py --check decides on results, not on where they
were made. CI runs a different Python patch release from the machine that
made the record, and that alone must not fail it; a changed result must, and
must say which."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "publish_campaign.py"
RECORD = ROOT / "assets" / "data" / "campaign.json"

pytestmark = pytest.mark.skipif(
    not (TOOL.exists() and RECORD.exists()), reason="tools not present (standalone harness checkout)"
)


def _tool():
    spec = importlib.util.spec_from_file_location("publish_campaign", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _record() -> dict:
    return json.loads(RECORD.read_text())


def test_another_environment_is_a_note_not_a_difference():
    rec, other = _record(), _record()
    other["generated"] = "2030-01-01"
    other["report"]["environment"]["python"] = "3.11.99"
    diffs, notes = _tool().compare(rec, other)
    assert diffs == []
    assert len(notes) == 1 and "3.11.99" in notes[0]


def test_a_changed_result_is_named_by_its_path():
    rec, other = _record(), _record()
    n = rec["report"]["failures_total"]
    other["report"]["failures_total"] = n + 1
    diffs, notes = _tool().compare(rec, other)
    assert diffs == [f"/report/failures_total: record {n}, engine {n + 1}"]
    assert notes == []


def test_a_point_that_moved_is_found_inside_a_list():
    rec, other = _record(), _record()
    other["scatter"]["points"][7]["f"] = 1 - rec["scatter"]["points"][7]["f"]
    diffs, _ = _tool().compare(rec, other)
    assert [d.split(":")[0] for d in diffs] == ["/scatter/points[7]/f"]


def test_tuples_from_the_engine_equal_lists_from_the_file():
    assert _tool().compare({"a": [1, 2]}, {"a": (1, 2)}) == ([], [])
