"""Every API test runs on SQLite, and on Postgres too when one is given:

    TEETER_TEST_DATABASE_URL=postgresql+psycopg://teeter@127.0.0.1:55432/teeter_test

The queue's correctness must not depend on which one is underneath.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from teeter_api.app import create_app
from teeter_api.db import Base, Database
from teeter_api.models import Membership, User, Workspace
from teeter_api.security import mint
from teeter_api.settings import Settings

PG = os.environ.get("TEETER_TEST_DATABASE_URL")
BACKENDS = ["sqlite"] + (["postgres"] if PG else [])

SPEC = {
    "robot": "quadruped", "policy": "stand", "duration_s": 5.0,
    "axes": {"push_impulse_ns": [0, 9], "slope_deg": [0, 10]},
    "predicates": [{"name": "tilt_limit", "signal": "tilt_deg", "op": ">", "threshold": 35.0, "grace_s": 0.3}],
    "search": {"method": "cem", "budget": 6},
    "reduce": {"max": 2},
}


@pytest.fixture(params=BACKENDS)
def db(request, tmp_path):
    if request.param == "postgres":
        d = Database(PG)
        with d.engine.begin() as conn:                       # a clean schema per test
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    else:
        d = Database(f"sqlite:///{tmp_path / 'test.sqlite'}")
    d.create_all()
    yield d
    d.engine.dispose()


@pytest.fixture
def settings(tmp_path):
    return Settings(database_url="unused", storage_dir=str(tmp_path / "storage"), site_dir="",
                    public_url="http://testserver", lease_s=30.0)


@pytest.fixture
def app(db, settings):
    return create_app(settings, db)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@dataclass
class World:
    db: Database
    workspace_id: str
    user: str
    ci: str
    runner: str
    runner2: str

    @staticmethod
    def h(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def world(db) -> World:
    with db.scope() as s:
        ws = Workspace(slug="acme", name="Acme (example)")
        s.add(ws)
        s.flush()
        u = User(email="owner@example.com")
        s.add(u)
        s.flush()
        s.add(Membership(workspace_id=ws.id, user_id=u.id, role="owner"))
        _, user = mint(s, ws, "user", "owner", user=u)
        _, ci = mint(s, ws, "ci", "ci")
        _, r1 = mint(s, ws, "runner", "r1")
        _, r2 = mint(s, ws, "runner", "r2")
        s.commit()
        return World(db, ws.id, user, ci, r1, r2)


def register(client, token, name="lab-1", robots=("quadruped",), policies=("stand", "tall")):
    r = client.post("/v1/runner/register", headers=World.h(token),
                    json={"name": name, "robots": list(robots), "policies": list(policies), "cores": 4,
                          "versions": {"mujoco": "3.12.0", "harness": "0.3.0"}})
    assert r.status_code == 200, r.text
    return r.json()


def evaluation(i, failed=False, push=1.0):
    return {"index": i, "iteration": i // 3, "perturbation": {"push_impulse_ns": push, "slope_deg": 0.0},
            "severity": 5.0 if failed else -5.0, "failed": failed,
            "violation": {"predicate": "tilt_limit", "first_t": 1.26} if failed else None}


def result(evaluations, modes=(), robot_sha="a" * 64, mujoco="3.12.0"):
    return {"harness": "0.3.0", "environment": {"mujoco": mujoco, "numpy": "2", "python": "3.11", "platform": "x"},
            "robot": {"name": "quadruped", "sha256": robot_sha}, "policy": {"name": "stand", "id": "stand-v1:abc"},
            "base_config_sha256": "b" * 64, "nominals": {"friction_mu": 0.9}, "evaluations": evaluations,
            "failures": sum(1 for m in modes for _ in range(m["count"])), "invalid": 0,
            "first_failure_index": 0 if modes else None, "elapsed_s": 1.0, "reduced": len(modes),
            "coverage": {"cells_visited": 3}, "modes": list(modes)}


def mode(push, required=("push_impulse_ns",), count=2, replay=None):
    return {"label": "tilt_limit via " + " + ".join(required), "predicate": "tilt_limit",
            "required": list(required), "count": count,
            "minimal": {"push_impulse_ns": push, "slope_deg": 0.0, "torque_loss_pct": 0.0},
            "first_t": 1.26, "locally_minimal": True, "evaluations": 18, "replay": replay}


def run_fake(client, runner_token, *, modes=(), robot_sha="a" * 64, mujoco="3.12.0"):
    """Claim one job and finish it with synthetic results, as a runner would."""
    got = client.post("/v1/runner/claim", headers=World.h(runner_token), json={"wait_s": 0})
    assert got.status_code == 200, got.text
    job = got.json()
    jid, budget = job["job"]["id"], job["campaign"]["spec"]["search"]["budget"]
    evs = [evaluation(i, failed=(i % 2 == 0) and bool(modes)) for i in range(budget)]
    r = client.post(f"/v1/runner/jobs/{jid}/evaluations", headers=World.h(runner_token), json={"evaluations": evs})
    assert r.status_code == 200, r.text
    r = client.post(f"/v1/runner/jobs/{jid}/complete", headers=World.h(runner_token),
                    json={"result": result(budget, modes, robot_sha, mujoco)})
    assert r.status_code == 200, r.text
    return job
