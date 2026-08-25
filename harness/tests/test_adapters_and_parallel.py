"""Exported checkpoints, and running a campaign on more than one core.

The determinism test here is the load-bearing one. Reproducibility is the
claim the whole product rests on, so a campaign run across workers must be
bit-identical to the same campaign run serially — not merely similar.
"""

from __future__ import annotations

import numpy as np
import mujoco
import pytest

from faultline.adapters import PolicyLoadError
from faultline.policies import StandPolicy
from faultline.search import cem_search, random_search
from faultline.space import SearchSpace
from faultline.spec import Predicate, RunSpec, Seeds

MODEL = "models/quadruped.xml"


@pytest.fixture(scope="module")
def spec():
    return RunSpec(
        model_path=MODEL, policy_id="stand",
        predicates=(Predicate("tilt_limit", "tilt_deg", ">", 35.0, 0.3),),
        seeds=Seeds(41279, 0, 0), duration_s=2.5,
    )


@pytest.fixture(scope="module")
def policy():
    return StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])


@pytest.fixture(scope="module")
def space():
    return SearchSpace({"push_impulse_ns": (0, 16), "slope_deg": (0, 12)})


def fingerprint(result):
    """Everything a downstream consumer could observe about a campaign."""
    return [
        (s.index, s.iteration, repr(s.severity), s.failed, s.invalid,
         tuple(sorted((k, repr(v)) for k, v in s.perturbation.items())))
        for s in result.samples
    ]


# ── parallelism ───────────────────────────────────────────────────────


@pytest.mark.parametrize("search", [random_search, cem_search])
def test_a_parallel_campaign_is_identical_to_a_serial_one(spec, policy, space, search):
    """Not 'similar'. A result that changes with the worker count would make
    every replay claim in the archive meaningless."""
    serial = search(spec, policy, space, budget=16, seed=7)
    parallel = search(spec, policy, space, budget=16, seed=7, workers=4)
    assert fingerprint(serial) == fingerprint(parallel)


def test_worker_count_does_not_change_the_verdict(spec, policy, space):
    counts = [1, 2, 3]
    prints = [fingerprint(cem_search(spec, policy, space, budget=12, seed=3, workers=w))
              for w in counts]
    assert all(p == prints[0] for p in prints)


def test_an_unpicklable_policy_says_what_to_pass_instead(spec, space):
    """An ONNX session cannot cross a process boundary. The error has to name
    the fix, because the alternative is a silent fall back to one core."""
    class Unpicklable:
        def __init__(self): self._lock = __import__("threading").Lock()
        def reset(self, seed): pass
        def act(self, obs, t): return np.zeros(12)

    with pytest.raises(ValueError, match="policy_ref"):
        random_search(spec, Unpicklable(), space, budget=4, seed=1, workers=2)


# ── exported checkpoints ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def onnx_dir(tmp_path_factory):
    """A real two-layer MLP, the shape a small policy exports to."""
    onnx = pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from onnx import TensorProto, helper

    d = tmp_path_factory.mktemp("onnx")
    rng = np.random.default_rng(0)

    def build(name, obs_dim, act_dim, noisy=False):
        W1 = (rng.standard_normal((obs_dim, 16)) * 0.3).astype(np.float32)
        W2 = (rng.standard_normal((16, act_dim)) * 0.3).astype(np.float32)
        nodes = [helper.make_node("MatMul", ["obs", "W1"], ["h"]),
                 helper.make_node("Tanh", ["h"], ["a"])]
        last = "a"
        if noisy:                       # dropout left enabled on export
            nodes += [helper.make_node("RandomNormalLike", ["a"], ["n"], scale=0.5),
                      helper.make_node("Add", ["a", "n"], ["an"])]
            last = "an"
        nodes.append(helper.make_node("MatMul", [last, "W2"], ["action"]))
        g = helper.make_graph(
            nodes, "p",
            [helper.make_tensor_value_info("obs", TensorProto.FLOAT, ["b", obs_dim])],
            [helper.make_tensor_value_info("action", TensorProto.FLOAT, ["b", act_dim])],
            [helper.make_tensor("W1", TensorProto.FLOAT, W1.shape, W1.ravel()),
             helper.make_tensor("W2", TensorProto.FLOAT, W2.shape, W2.ravel())])
        m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
        m.ir_version = 10
        p = d / f"{name}.onnx"
        onnx.save(m, p)
        return p

    return {
        "good": build("good", 30, 12),
        "noisy": build("noisy", 30, 12, noisy=True),
        "narrow": build("narrow", 30, 7),
    }


def test_identity_is_the_file_content_not_its_path(onnx_dir, tmp_path):
    """A checkpoint path gets overwritten; a run history keyed on it is a lie
    about which network produced which result."""
    from faultline.adapters import OnnxPolicy

    a = OnnxPolicy(onnx_dir["good"], n_actions=12)
    copy = tmp_path / "renamed.onnx"
    copy.write_bytes(onnx_dir["good"].read_bytes())
    b = OnnxPolicy(copy, n_actions=12)
    assert a.sha256 == b.sha256
    assert a.id.endswith(a.sha256[:12])


def test_a_nondeterministic_export_is_refused(onnx_dir):
    """Dropout left on makes every reproducibility claim downstream false,
    and nothing else in the pipeline would notice."""
    from faultline.adapters import OnnxPolicy

    with pytest.raises(PolicyLoadError, match="not deterministic"):
        OnnxPolicy(onnx_dir["noisy"], n_actions=12)


def test_a_mismatched_action_width_is_caught(onnx_dir):
    from faultline.adapters import OnnxPolicy

    p = OnnxPolicy(onnx_dir["narrow"], n_actions=12)
    with pytest.raises(PolicyLoadError, match="returned 7 action"):
        p.act(np.zeros(30), 0.0)


def test_a_missing_runtime_names_the_extra_to_install(tmp_path, monkeypatch):
    """Someone testing an ONNX policy should not be made to install PyTorch,
    so both runtimes are extras and the error has to say which."""
    import builtins

    from faultline.adapters import TorchScriptPolicy

    p = tmp_path / "policy.pt"
    p.write_bytes(b"not really a checkpoint")
    real = builtins.__import__

    def no_torch(name, *a, **k):
        if name == "torch":
            raise ImportError("no module named torch")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_torch)
    with pytest.raises(PolicyLoadError, match=r"faultline-harness\[torch\]"):
        TorchScriptPolicy(p)


def test_an_onnx_policy_survives_the_worker_boundary(onnx_dir, space):
    """The reason policy_ref exists: the session itself cannot be pickled, so
    each worker rebuilds one from the reference."""
    pytest.importorskip("onnxruntime")
    from faultline.config import load_policy

    ref = f"onnx:{onnx_dir['good']}"
    pol = load_policy(ref, MODEL)
    s = RunSpec(
        model_path=MODEL, policy_id=pol.id,
        predicates=(Predicate("tilt_limit", "tilt_deg", ">", 35.0, 0.3),),
        seeds=Seeds(41279, 0, 0), duration_s=2.0,
        observation=({"term": "projected_gravity"}, {"term": "base_ang_vel"},
                     {"term": "joint_pos", "relative": True},
                     {"term": "joint_vel", "scale": 0.05}),
    )
    serial = cem_search(s, pol, space, budget=12, seed=5)
    parallel = cem_search(s, pol, space, budget=12, seed=5, workers=3, policy_ref=ref)
    assert fingerprint(serial) == fingerprint(parallel)
