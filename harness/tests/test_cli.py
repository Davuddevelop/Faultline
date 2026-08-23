"""The command line and the config format.

The claim being tested is that someone who is not us can install this and run
a campaign. `init` writing a file that `run` accepts is the load-bearing one:
it means the quickstart cannot rot.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import Predicate, RunSpec, SearchSpace, Seeds  # noqa: E402
from faultline.cli import build_parser, main  # noqa: E402
from faultline.config import ConfigError, load, load_policy  # noqa: E402

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")

MINIMAL = """
robot: __MODEL__
policy: stand
duration_s: 3.0
seeds: {sampler: 7, sim: 0, policy: 0}
axes:
  push_impulse_ns: [0, 9]
  slope_deg: [0, 10]
predicates:
  - {name: tilt_limit, signal: tilt_deg, op: ">", threshold: 35.0, grace_s: 0.3}
search: {method: cem, budget: 8}
reduce: {enabled: true, max: 2, budget: 40}
"""


def write(tmp_path: Path, body: str, name: str = "c.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body.replace("__MODEL__", MODEL))
    return p


# ------------------------------------------------------------------ parsing

def test_config_produces_the_same_spec_as_the_python_equivalent(tmp_path):
    """The YAML is a different way to say the same thing, not a second
    definition of what a campaign is."""
    campaign = load(write(tmp_path, MINIMAL))

    equivalent = RunSpec(
        model_path=MODEL, policy_id="stand", duration_s=3.0,
        seeds=Seeds(sampler=7, sim=0, policy=0),
        predicates=(Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),),
    )
    assert campaign.spec.config_hash() == equivalent.config_hash()
    assert campaign.space.as_dict() == SearchSpace(
        {"push_impulse_ns": (0, 9), "slope_deg": (0, 10)}
    ).as_dict()
    assert campaign.method == "cem" and campaign.budget == 8


def test_relative_robot_path_resolves_against_the_config(tmp_path):
    (tmp_path / "sub").mkdir()
    model_copy = tmp_path / "sub" / "robot.xml"
    model_copy.write_text(Path(MODEL).read_text())
    cfg = tmp_path / "sub" / "c.yaml"
    cfg.write_text(MINIMAL.replace("__MODEL__", "robot.xml"))
    assert load(cfg).spec.model_path == str(model_copy.resolve())


# ------------------------------------------------------- loud, specific errors

def test_missing_robot_is_named(tmp_path):
    body = MINIMAL.replace("robot: __MODEL__\n", "")
    with pytest.raises(ConfigError, match="missing required key 'robot'"):
        load(write(tmp_path, body))


def test_unknown_top_level_key_is_named(tmp_path):
    with pytest.raises(ConfigError, match="unknown key.*flavour"):
        load(write(tmp_path, MINIMAL + "flavour: strawberry\n"))


def test_unknown_axis_is_named(tmp_path):
    body = MINIMAL.replace("  slope_deg: [0, 10]", "  wind_speed: [0, 10]")
    with pytest.raises(ConfigError, match="not a searchable axis"):
        load(write(tmp_path, body))


def test_bad_predicate_operator_is_named(tmp_path):
    body = MINIMAL.replace('op: ">"', 'op: ">="')
    with pytest.raises(ConfigError, match=r"predicates\[0\]"):
        load(write(tmp_path, body))


def test_a_campaign_with_no_predicates_is_refused(tmp_path):
    body = MINIMAL[:MINIMAL.index("predicates:")] + "search: {method: cem, budget: 4}\n"
    with pytest.raises(ConfigError, match="at least one predicate"):
        load(write(tmp_path, body))


def test_search_target_must_be_a_declared_predicate(tmp_path):
    body = MINIMAL.replace("search: {method: cem, budget: 8}",
                           "search: {method: cem, budget: 8, target: nope}")
    with pytest.raises(ConfigError, match="not a declared predicate"):
        load(write(tmp_path, body))


def test_unknown_search_method_is_refused(tmp_path):
    body = MINIMAL.replace("method: cem", "method: telepathy")
    with pytest.raises(ConfigError, match="must be 'cem' or 'random'"):
        load(write(tmp_path, body))


def test_a_missing_robot_file_is_reported_not_crashed(tmp_path):
    body = MINIMAL.replace("__MODEL__", "/nowhere/robot.xml")
    with pytest.raises(ConfigError, match="robot model not found"):
        load(write(tmp_path, body))


def test_malformed_yaml_is_reported_as_such(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("robot: [unclosed\n")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load(p)


# -------------------------------------------------------------- policy loading

def test_the_stand_alias_loads_the_baseline():
    policy = load_policy("stand", MODEL)
    assert callable(policy.reset) and callable(policy.act)


def test_a_policy_without_a_colon_is_refused():
    with pytest.raises(ConfigError, match="module:Attr"):
        load_policy("mypolicy", MODEL)


def test_an_unimportable_policy_module_is_named():
    with pytest.raises(ConfigError, match="cannot import policy module"):
        load_policy("no_such_module_xyz:Thing", MODEL)


def test_a_missing_attribute_is_named():
    with pytest.raises(ConfigError, match="no attribute"):
        load_policy("faultline.policies:NotAPolicy", MODEL)


# ------------------------------------------------------------------ the CLI

def test_init_writes_a_file_that_run_accepts(tmp_path):
    """The quickstart cannot rot: whatever `init` emits must parse."""
    out = tmp_path / "campaign.yaml"
    assert main(["init", str(out)]) == 0
    assert out.exists()

    campaign = load(out)                       # would raise if the starter drifted
    assert campaign.space.dims >= 3
    assert campaign.spec.predicates


def test_init_refuses_to_clobber_without_force(tmp_path, capsys):
    out = tmp_path / "campaign.yaml"
    assert main(["init", str(out)]) == 0
    assert main(["init", str(out)]) == 2
    assert "already exists" in capsys.readouterr().err
    assert main(["init", str(out), "--force"]) == 0


def test_run_writes_all_three_deliverables_and_exits_1_on_violations(tmp_path):
    cfg = write(tmp_path, MINIMAL)
    # 24 simulations in this space finds nothing; 40 reliably does
    code = main(["run", str(cfg), "--budget", "40", "--out", str(tmp_path / "out"), "-q"])
    assert code == 1                            # violations found

    out = tmp_path / "out"
    assert (out / "engineering-report.md").exists()
    assert (out / "safety-appendix.md").exists()
    assert (out / "archive" / "manifest.jsonl").exists()

    doc = json.loads((out / "archive" / "report.json").read_text())
    assert doc["modes"]


def test_run_exits_0_when_nothing_violates(tmp_path):
    """Exit codes are what make this composable in CI."""
    body = MINIMAL.replace("push_impulse_ns: [0, 9]", "push_impulse_ns: [0, 0.4]") \
                  .replace("slope_deg: [0, 10]", "slope_deg: [0, 0.4]")
    cfg = write(tmp_path, body, "quiet.yaml")
    assert main(["run", str(cfg), "--budget", "6", "--out", str(tmp_path / "o"), "-q"]) == 0


def test_a_bad_config_exits_2_with_a_message_not_a_traceback(tmp_path, capsys):
    p = tmp_path / "bad.yaml"
    p.write_text("robot: /nowhere.xml\npolicy: stand\n")
    assert main(["run", str(p)]) == 2
    assert "error:" in capsys.readouterr().err


def test_version_reports_everything_that_affects_a_result(capsys):
    assert main(["version"]) == 0
    out = capsys.readouterr().out
    for field in ("faultline", "mujoco", "numpy", "platform"):
        assert field in out


def test_every_subcommand_is_reachable():
    parser = build_parser()
    for cmd in ("init", "run", "replay", "version"):
        assert parser.parse_args([cmd] if cmd != "replay" else [cmd, "x.json"])


# --------------------------------------------------- the page and the code agree

def test_the_config_shown_on_the_landing_page_is_a_real_campaign(tmp_path):
    """The site displays a campaign.yaml. It must be a config this code can
    actually load, or the page is showing a mock-up of its own product.

    Skipped when the harness is installed on its own, away from the site.
    """
    import re
    from html import unescape

    page = Path(__file__).resolve().parents[2] / "index.html"
    if not page.exists():
        pytest.skip("landing page not present; harness checked out standalone")

    block = re.search(
        r'<pre class="config__body mono"><code>(.*?)</code></pre>',
        page.read_text(), re.S,
    )
    assert block, "the landing page no longer shows a config block"

    text = unescape(re.sub(r"<[^>]+>", "", block.group(1)))
    # the page shows a customer's own files; point those two at real ones
    text = text.replace("my_robot.urdf", MODEL).replace(
        "mypkg.policies:WalkPolicy", "stand")

    cfg = tmp_path / "from_page.yaml"
    cfg.write_text(text)

    campaign = load(cfg)                       # raises if the page has drifted
    assert campaign.space.dims >= 3
    assert campaign.spec.predicates
    assert campaign.method in ("cem", "random")
