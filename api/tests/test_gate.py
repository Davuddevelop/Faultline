"""What the gate says, and when it refuses to say anything."""

from __future__ import annotations

import pytest

from conftest import SPEC, World, mode, register, run_fake
from teeter_api import gate


def _c(spec_over=None, modes=(), sha="a" * 64, mujoco="3.12.0"):
    spec = {**SPEC, **(spec_over or {})}
    return {"spec": spec, "result": {"robot": {"sha256": sha}, "environment": {"mujoco": mujoco},
                                     "nominals": {"friction_mu": 0.9}, "modes": list(modes)}}


def test_a_smaller_condition_is_widened_and_blocks():
    g = gate.compare(_c(modes=[mode(7.9)]), _c({"policy": "tall"}, modes=[mode(6.2)]))
    assert g["verdict"] == "blocked" and g["modes"][0]["change"] == "widened"


def test_within_tolerance_is_unchanged_and_passes():
    g = gate.compare(_c(modes=[mode(7.9)]), _c({"policy": "tall"}, modes=[mode(7.6)]))   # tolerance 0.5
    assert g["verdict"] == "passed" and g["modes"][0]["change"] == "unchanged"


def test_a_larger_condition_is_narrowed():
    g = gate.compare(_c(modes=[mode(6.0)]), _c({"policy": "crouch"}, modes=[mode(8.5)]))
    assert g["verdict"] == "passed" and g["modes"][0]["change"] == "narrowed"


def test_a_new_mode_blocks_and_a_missing_one_is_only_not_found():
    base = _c(modes=[mode(7.9, ("push_impulse_ns",))])
    cand = _c({"policy": "tall"}, modes=[mode(5.0, ("push_impulse_ns", "slope_deg"))])
    g = gate.compare(base, cand)
    changes = {tuple(r["required"]): r["change"] for r in g["modes"]}
    assert changes == {("push_impulse_ns", "slope_deg"): "new", ("push_impulse_ns",): "not_found"}
    assert g["verdict"] == "blocked"
    assert "fixed" not in str(g), "not finding a mode is not evidence it is gone"


@pytest.mark.parametrize("over,needle", [
    ({"axes": {"push_impulse_ns": [0, 12], "slope_deg": [0, 10]}}, "axes"),
    ({"seeds": {"sampler": 1, "sim": 0, "policy": 0}}, "seeds"),
    ({"duration_s": 6.0}, "duration_s"),
])
def test_a_different_experiment_is_refused_and_named(over, needle):
    g = gate.compare(_c(modes=[mode(7.9)]), _c({"policy": "tall", **over}, modes=[mode(6.0)]))
    assert g["verdict"] == "refused" and any(needle in d for d in g["differs"])


def test_a_different_robot_file_or_simulator_is_refused():
    assert gate.compare(_c(), _c({"policy": "tall"}, sha="b" * 64))["verdict"] == "refused"
    assert gate.compare(_c(), _c({"policy": "tall"}, mujoco="3.13.0"))["verdict"] == "refused"


def test_gating_a_checkpoint_through_its_program(client, world):
    u, ci = World.h(world.user), World.h(world.ci)
    std = {k: v for k, v in SPEC.items() if k != "policy"}
    assert client.post("/v1/programs", headers=u, json={"slug": "q2", "name": "Q2", "standard_spec": std}).status_code == 201
    client.post("/v1/programs/q2/checkpoints", headers=u, json={"label": "v40", "policy": "stand", "baseline": True})
    client.post("/v1/programs/q2/checkpoints", headers=u, json={"label": "v41", "policy": "tall"})

    g = client.post("/v1/programs/q2/gate", headers=ci, json={"checkpoint": "v41"})
    assert g.status_code == 201, g.text
    g = g.json()
    assert g["state"] == "waiting" and g["baseline"]["policy"] == "stand" and g["candidate"]["policy"] == "tall"

    register(client, world.runner)
    run_fake(client, world.runner, modes=[mode(7.9)])          # the baseline, queued first
    assert client.get(f"/v1/gates/{g['ref']}", headers=ci).json()["state"] == "waiting"
    run_fake(client, world.runner, modes=[mode(6.2)])          # the candidate
    done = client.get(f"/v1/gates/{g['ref']}", headers=ci).json()
    assert done["state"] == "decided" and done["verdict"] == "blocked"
    assert done["comparison"]["modes"][0]["axes"][0]["baseline"] == 7.9

    # a second gate reuses the baseline's finished run of the same experiment
    g2 = client.post("/v1/programs/q2/gate", headers=ci, json={"checkpoint": "v41"}).json()
    assert g2["baseline"]["ref"] == g["baseline"]["ref"]


def test_a_failed_campaign_refuses_its_gate(client, world):
    u = World.h(world.user)
    client.post("/v1/campaigns", headers=u, json={"spec": SPEC})
    client.post("/v1/campaigns", headers=u, json={"spec": {**SPEC, "policy": "tall"}})
    g = client.post("/v1/gates", headers=u, json={"baseline": "C-0001", "candidate": "C-0002"}).json()
    register(client, world.runner)
    run_fake(client, world.runner, modes=[mode(7.9)])
    j = client.post("/v1/runner/claim", headers=World.h(world.runner), json={"wait_s": 0}).json()["job"]["id"]
    client.post(f"/v1/runner/jobs/{j}/fail", headers=World.h(world.runner), json={"error": "policy file missing"})
    out = client.get(f"/v1/gates/{g['ref']}", headers=u).json()
    assert out["verdict"] == "refused" and "C-0002 failed" in out["comparison"]["reason"]
