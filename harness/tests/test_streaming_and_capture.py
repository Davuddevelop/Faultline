"""What the runner needs from the engine, as tests.

A control plane streams a campaign as it runs, builds a campaign from data
rather than a file, and replays a failure in 3D. Each must be the same campaign
the CLI would have run, not a near copy of it.
"""

from __future__ import annotations

from pathlib import Path

import mujoco
import pytest

from faultline import Predicate, RunSpec, Seeds, StandPolicy, cem_search, random_search, run
from faultline.capture import quadruped_replay, supports_replay
from faultline.config import ConfigError, load, parse
from faultline.space import SearchSpace

MODEL = str(Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")
PREDS = (Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),)
SPACE = SearchSpace({"push_impulse_ns": (0.0, 12.0), "slope_deg": (0.0, 8.0)})


@pytest.fixture(scope="module")
def policy():
    return StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])


def _spec(policy):
    return RunSpec(model_path=MODEL, policy_id=policy.id, predicates=PREDS,
                   seeds=Seeds(3, 0, 0), duration_s=2.0)


@pytest.mark.parametrize("search", [random_search, cem_search])
def test_progress_sees_every_sample_in_order(policy, search):
    seen = []
    result = search(_spec(policy), policy, SPACE, budget=12, seed=3, progress=seen.append)
    assert [s.index for s in seen] == list(range(12))
    assert [s.as_dict() for s in seen] == [s.as_dict() for s in result.samples]


def test_progress_is_identical_across_workers(policy):
    one, two = [], []
    cem_search(_spec(policy), policy, SPACE, budget=12, seed=3, progress=one.append)
    cem_search(_spec(policy), policy, SPACE, budget=12, seed=3, workers=2,
               policy_ref="stand", progress=two.append)
    assert [s.as_dict() for s in one] == [s.as_dict() for s in two]


def test_raising_from_progress_stops_the_campaign(policy):
    class Stop(Exception):
        pass

    def stop_after_five(sample):
        if sample.index == 4:
            raise Stop

    with pytest.raises(Stop):
        random_search(_spec(policy), policy, SPACE, budget=40, seed=3, progress=stop_after_five)


def test_parse_is_load_without_the_file(tmp_path):
    doc = {"robot": MODEL, "policy": "stand", "duration_s": 2.0,
           "axes": {"push_impulse_ns": [0, 9]},
           "predicates": [{"name": "tilt_limit", "signal": "tilt_deg", "op": ">", "threshold": 35.0}]}
    import yaml
    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(doc))
    a, b = load(path), parse(doc, base_dir=tmp_path, source="api")
    assert a.spec.config_hash() == b.spec.config_hash()
    assert (a.space.as_dict(), a.budget, a.method) == (b.space.as_dict(), b.budget, b.method)
    with pytest.raises(ConfigError, match="api: unknown key"):
        parse({**doc, "robto": 1}, base_dir=tmp_path, source="api")


def test_a_replay_is_the_run_that_produced_the_result(policy):
    s = _spec(policy).with_perturbation(push_impulse_ns=9.0)
    replay = quadruped_replay(s, policy, threshold=35.0)
    assert replay is not None and replay["format"] == "teeter-replay/1"
    tilt = run(s, policy).tilt_deg
    assert replay["runs"]["minimal"]["tilt"] == [round(float(v), 2) for v in tilt]
    assert len(replay["runs"]["minimal"]["f"]) == len(tilt)
    assert len(replay["runs"]["minimal"]["f"][0]) == 7 + 4 * 12
    assert replay["runs"]["nominal"]["perturbation"]["push_impulse_ns"] == 0.0


def test_a_robot_not_built_like_the_quadruped_gets_no_replay(tmp_path):
    from test_model_and_observe import ARM
    p = tmp_path / "arm.xml"
    p.write_text(ARM)
    assert supports_replay(MODEL)
    assert not supports_replay(p)


def test_uniform_sampling_spends_one_draw_per_point(policy):
    """Regression: points were built with space.sample() called once per axis,
    six draws per point, so the published record could not be re-made and the
    uniform arm no longer opened on the directed search's first-round points."""
    import numpy as np
    r = random_search(_spec(policy), policy, SPACE, budget=10, seed=7)
    expected = np.random.default_rng(7).uniform(SPACE.lo(), SPACE.hi(), size=(10, SPACE.dims))
    got = np.array([[s.perturbation[a] for a in SPACE.axes] for s in r.samples])
    assert np.allclose(got, expected)
    directed = cem_search(_spec(policy), policy, SPACE, budget=12, seed=7, iterations=2)
    assert [s.perturbation for s in directed.samples[:6]] == [s.perturbation for s in r.samples[:6]]
