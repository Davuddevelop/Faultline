"""The runner against a real API server, on real physics.

The server runs in a thread on a random port with a temporary SQLite
database; the runner is the real Agent, claiming over HTTP. Nothing is
mocked: these are the demo's moving parts, small enough to run in a test.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from teeter_api.app import create_app
from teeter_api.db import Database
from teeter_api.models import Checkpoint, Membership, Program, User, Workspace
from teeter_api.security import mint
from teeter_api.settings import Settings
from teeter_runner.agent import Agent
from teeter_runner.cli import main as teeter
from teeter_runner.config import load as load_config

HERE = Path(__file__).resolve().parent
SPEC = {
    "robot": "quadruped", "duration_s": 3.0,
    "axes": {"push_impulse_ns": [0.0, 12.0]},
    "predicates": [{"name": "tilt_limit", "signal": "tilt_deg", "op": ">", "threshold": 35.0, "grace_s": 0.3}],
    "search": {"method": "cem", "budget": 18, "workers": 1},
    "reduce": {"max": 2, "budget": 40},
}


@pytest.fixture
def server(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'e2e.sqlite'}")
    settings = Settings(database_url="unused", storage_dir=str(tmp_path / "storage"), site_dir="", lease_s=20)
    app = create_app(settings, db)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    with db.scope() as s:
        ws = Workspace(slug="e2e", name="E2E (example)")
        s.add(ws)
        s.flush()
        u = User(email="e2e@example.com")
        s.add(u)
        s.flush()
        s.add(Membership(workspace_id=ws.id, user_id=u.id, role="owner"))
        _, user = mint(s, ws, "user", "owner", user=u)
        _, runner = mint(s, ws, "runner", "runner")
        _, ci = mint(s, ws, "ci", "ci")
        prog = Program(workspace_id=ws.id, slug="quad", name="Quad", standard_spec={**SPEC, "policy": None})
        s.add(prog)
        s.flush()
        for label, policy, base in (("stand-v1", "stand", True), ("tall-v2", "tall", False)):
            ck = Checkpoint(workspace_id=ws.id, program_id=prog.id, label=label, policy=policy)
            s.add(ck)
            s.flush()
            if base:
                prog.baseline_checkpoint_id = ck.id
        s.commit()
    yield {"api": f"http://127.0.0.1:{port}", "user": user, "runner": runner, "ci": ci}
    srv.should_exit = True
    t.join(timeout=10)


def _runner(server, logs):
    cfg = load_config(HERE.parent / "demo-runner.yaml")
    return Agent(server["api"], server["runner"], cfg, name="test-runner", log=logs.append)


def test_a_campaign_runs_on_a_real_runner_and_comes_back_complete(server):
    h = {"Authorization": f"Bearer {server['user']}"}
    made = httpx.post(f"{server['api']}/v1/campaigns", headers=h, json={"spec": {**SPEC, "policy": "stand"}})
    assert made.status_code == 201, made.text
    logs: list[str] = []
    assert _runner(server, logs).run_forever(once=True, wait_s=1) == 0, logs

    c = httpx.get(f"{server['api']}/v1/campaigns/C-0001", headers=h).json()
    assert c["state"] == "done", (c.get("error"), logs)
    assert c["evaluations"] == 18 and c["runner"] == "test-runner"
    assert c["result"]["environment"]["mujoco"] and c["result"]["robot"]["sha256"]
    assert c["failures"] > 0 and c["modes"], "pushes up to 12 N.s must topple the stand-in"
    m = c["modes"][0]
    assert m["required"] == ["push_impulse_ns"] and m["replay"] and m["trace"]

    evs = httpx.get(f"{server['api']}/v1/campaigns/C-0001/evaluations", headers=h).json()["evaluations"]
    assert [e["index"] for e in evs] == list(range(18))
    replay = httpx.get(f"{server['api']}/v1/campaigns/C-0001/artifacts/{m['replay']}", headers=h).json()
    assert replay["format"] == "teeter-replay/1" and len(replay["runs"]["minimal"]["f"]) == 150
    tilt = replay["runs"]["minimal"]["tilt"]
    breach = next(i for i, v in enumerate(tilt) if v > 35.0) / 50
    assert abs(breach - m["first_t"]) < 0.021, "the replay must be the run the mode reports"


def test_the_runner_refuses_what_its_allowlist_does_not_name(server):
    h = {"Authorization": f"Bearer {server['user']}"}
    bad = {**SPEC, "policy": "stand", "robot": "quadruped"}
    httpx.post(f"{server['api']}/v1/campaigns", headers=h, json={"spec": bad})
    cfg = load_config(HERE.parent / "demo-runner.yaml")
    cfg.robots["quadruped"] = Path("/nonexistent/robot.xml")       # listed, but the file is gone
    logs: list[str] = []
    Agent(server["api"], server["runner"], cfg, name="test-runner", log=logs.append).run_forever(once=True, wait_s=1)
    c = httpx.get(f"{server['api']}/v1/campaigns/C-0001", headers=h).json()
    assert c["state"] == "failed" and "robot model not found" in c["error"]


def test_teeter_gate_blocks_a_checkpoint_that_got_worse(server, capsys):
    """stand-v1 is the baseline; tall-v2 holds a pose with a higher centre of
    mass and topples under a smaller push. The gate must say so, and exit 1."""
    stop = threading.Event()
    logs: list[str] = []
    agent = _runner(server, logs)

    def work():
        agent.register()
        while not stop.is_set():
            job = agent.client.claim(wait_s=1)
            if job:
                agent.run_job(job)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    try:
        code = teeter(["gate", "--api", server["api"], "--token", server["ci"],
                       "--program", "quad", "--checkpoint", "tall-v2", "--timeout", "240"])
    finally:
        stop.set()
        t.join(timeout=60)
    out = capsys.readouterr().out
    assert code == 1, (out, logs)
    assert "BLOCKED" in out and "widened" in out
