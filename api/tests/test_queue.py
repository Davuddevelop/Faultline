"""The queue's promises, tested where they could break: under concurrency,
when a runner dies, and when a dead runner comes back."""

from __future__ import annotations

import threading
from datetime import timedelta

from sqlalchemy import select, update

from conftest import SPEC, World, evaluation, register
from teeter_api import queue
from teeter_api.db import utcnow
from teeter_api.models import Campaign, Job, Runner, Workspace
from teeter_api.security import mint


def _expire(db, job_id):
    with db.scope() as s:
        s.execute(update(Job).where(Job.id == job_id).values(lease_expires_at=utcnow() - timedelta(seconds=1)))
        s.commit()


def test_many_runners_claiming_at_once_take_each_job_exactly_once(client, world, db):
    u = World.h(world.user)
    for _ in range(24):
        assert client.post("/v1/campaigns", headers=u, json={"spec": SPEC}).status_code == 201
    with db.scope() as s:
        ws = s.get(Workspace, world.workspace_id)
        runner_ids = []
        for i in range(8):
            tok, _ = mint(s, ws, "runner", f"r{i}")
            r = Runner(workspace_id=ws.id, token_id=tok.id, name=f"r{i}", robots=["quadruped"], policies=["stand"])
            s.add(r)
            s.flush()
            runner_ids.append(r.id)
        s.commit()

    taken, errors = [], []

    def worker(rid):
        try:
            with db.scope() as s:
                runner = s.get(Runner, rid)
                while True:
                    job = queue.claim(s, runner, 60, is_postgres=db.is_postgres)
                    if job is None:
                        return
                    taken.append((job.id, rid))
        except Exception as exc:              # surfaced below rather than lost in a thread
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(rid,)) for rid in runner_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    ids = [j for j, _ in taken]
    assert len(ids) == 24 and len(set(ids)) == 24, "a job was handed to two runners, or one was lost"


def test_a_runner_only_gets_jobs_it_allows(client, world):
    u = World.h(world.user)
    client.post("/v1/campaigns", headers=u, json={"spec": {**SPEC, "policy": "crouch"}})
    register(client, world.runner, policies=("stand",))
    assert client.post("/v1/runner/claim", headers=World.h(world.runner), json={"wait_s": 0}).status_code == 204
    register(client, world.runner2, name="lab-2", policies=("crouch",))
    assert client.post("/v1/runner/claim", headers=World.h(world.runner2), json={"wait_s": 0}).status_code == 200


def test_a_dead_runners_job_goes_to_the_next_and_starts_over(client, world, db):
    u, r1, r2 = World.h(world.user), World.h(world.runner), World.h(world.runner2)
    client.post("/v1/campaigns", headers=u, json={"spec": SPEC})
    register(client, world.runner)
    register(client, world.runner2, name="lab-2")
    j1 = client.post("/v1/runner/claim", headers=r1, json={"wait_s": 0}).json()["job"]["id"]
    client.post(f"/v1/runner/jobs/{j1}/evaluations", headers=r1,
                json={"evaluations": [evaluation(i) for i in range(3)]})

    _expire(db, j1)                                   # runner 1 stopped sending heartbeats
    took = client.post("/v1/runner/claim", headers=r2, json={"wait_s": 0}).json()
    assert took["job"]["id"] == j1 and took["job"]["attempt"] == 2
    c = client.get("/v1/campaigns/C-0001", headers=u).json()
    assert c["evaluations"] == 0, "a retry must not keep the first attempt's evaluations"
    assert c["runner"] == "lab-2"

    # runner 1 comes back: every job call is refused, so it cannot write into the retry
    late = client.post(f"/v1/runner/jobs/{j1}/evaluations", headers=r1, json={"evaluations": [evaluation(0)]})
    assert late.status_code == 409 and late.json()["error"]["code"] == "lease_lost"
    assert client.post(f"/v1/runner/jobs/{j1}/heartbeat", headers=r1, json={}).status_code == 409


def test_a_slow_runner_keeps_its_job_if_nobody_took_it(client, world, db):
    r1 = World.h(world.runner)
    client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": SPEC})
    register(client, world.runner)
    j1 = client.post("/v1/runner/claim", headers=r1, json={"wait_s": 0}).json()["job"]["id"]
    _expire(db, j1)
    hb = client.post(f"/v1/runner/jobs/{j1}/heartbeat", headers=r1, json={})
    assert hb.status_code == 200 and hb.json()["held"] is True


def test_a_job_that_keeps_dying_fails_with_a_reason(client, world, db):
    u, r1 = World.h(world.user), World.h(world.runner)
    client.post("/v1/campaigns", headers=u, json={"spec": SPEC})
    register(client, world.runner)
    for attempt in (1, 2, 3):
        got = client.post("/v1/runner/claim", headers=r1, json={"wait_s": 0})
        assert got.status_code == 200 and got.json()["job"]["attempt"] == attempt
        _expire(db, got.json()["job"]["id"])
    assert client.post("/v1/runner/claim", headers=r1, json={"wait_s": 0}).status_code == 204
    c = client.get("/v1/campaigns/C-0001", headers=u).json()
    assert c["state"] == "failed" and "heartbeats" in c["error"]


def test_a_retryable_failure_requeues_and_a_fatal_one_does_not(client, world):
    u, r1 = World.h(world.user), World.h(world.runner)
    client.post("/v1/campaigns", headers=u, json={"spec": SPEC})
    register(client, world.runner)
    j = client.post("/v1/runner/claim", headers=r1, json={"wait_s": 0}).json()["job"]["id"]
    client.post(f"/v1/runner/jobs/{j}/fail", headers=r1, json={"error": "network blip", "retryable": True})
    assert client.get("/v1/campaigns/C-0001", headers=u).json()["state"] == "queued"
    j = client.post("/v1/runner/claim", headers=r1, json={"wait_s": 0}).json()["job"]["id"]
    client.post(f"/v1/runner/jobs/{j}/fail", headers=r1,
                json={"error": "robot 'quadruped' is not in this runner's allowlist"})
    c = client.get("/v1/campaigns/C-0001", headers=u).json()
    assert c["state"] == "failed" and "allowlist" in c["error"]


def test_the_counters_match_a_recount(client, world, db):
    client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": {**SPEC, "search": {"budget": 50}}})
    register(client, world.runner)
    r1 = World.h(world.runner)
    j = client.post("/v1/runner/claim", headers=r1, json={"wait_s": 0}).json()["job"]["id"]
    for lo in range(0, 50, 7):                       # ragged, overlapping batches
        client.post(f"/v1/runner/jobs/{j}/evaluations", headers=r1,
                    json={"evaluations": [evaluation(i, failed=i % 3 == 0) for i in range(max(0, lo - 2), min(50, lo + 7))]})
    with db.scope() as s:
        c = s.scalar(select(Campaign))
        exact = queue.counts(s, c.id)
        assert (c.n_evaluations, c.n_failures) == (exact["evaluations"], exact["failures"]) == (50, 17)
        assert c.first_failure_index == 0
