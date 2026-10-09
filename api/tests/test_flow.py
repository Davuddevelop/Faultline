"""A campaign from the app's point of view: plan it, watch it, read it."""

from __future__ import annotations

from conftest import SPEC, World, evaluation, mode, register, result


def test_a_campaign_runs_end_to_end(client, world):
    u, r = World.h(world.user), World.h(world.runner)
    made = client.post("/v1/campaigns", headers=u, json={"spec": SPEC})
    assert made.status_code == 201, made.text
    c = made.json()
    assert c["ref"] == "C-0001" and c["state"] == "queued"

    register(client, world.runner)
    job = client.post("/v1/runner/claim", headers=r, json={"wait_s": 0}).json()
    assert job["campaign"]["ref"] == "C-0001" and job["job"]["attempt"] == 1
    jid = job["job"]["id"]
    assert client.get("/v1/campaigns/C-0001", headers=u).json()["state"] == "running"

    # stream in two batches, the second overlapping the first: ingest is idempotent
    b1 = client.post(f"/v1/runner/jobs/{jid}/evaluations", headers=r,
                     json={"evaluations": [evaluation(i, failed=i == 2) for i in range(4)]}).json()
    b2 = client.post(f"/v1/runner/jobs/{jid}/evaluations", headers=r,
                     json={"evaluations": [evaluation(i, failed=i in (2, 5)) for i in range(2, 6)]}).json()
    assert (b1["accepted"], b2["accepted"]) == (4, 2)
    assert (b2["evaluations_total"], b2["failures_total"]) == (6, 2)

    page = client.get("/v1/campaigns/C-0001/evaluations?after=3", headers=u).json()
    assert [e["index"] for e in page["evaluations"]] == [4, 5]
    assert page["next_after"] == 5 and page["first_failure_index"] == 2

    hb = client.post(f"/v1/runner/jobs/{jid}/heartbeat", headers=r, json={"progress": {"phase": "reduce"}})
    assert hb.json() == {**hb.json(), "held": True, "cancel": False}

    up = client.put(f"/v1/runner/jobs/{jid}/artifacts/modes/0/replay.json", headers={**r, "Content-Type": "application/json"},
                    content=b'{"format": "teeter-replay/1"}')
    assert up.status_code == 201, up.text
    done = client.post(f"/v1/runner/jobs/{jid}/complete", headers=r,
                       json={"result": result(6, [mode(7.875, replay="modes/0/replay.json")])})
    assert done.status_code == 200, done.text

    c = client.get("/v1/campaigns/C-0001", headers=u).json()
    assert c["state"] == "done" and c["modes"][0]["minimal"]["push_impulse_ns"] == 7.875
    assert c["result"]["environment"]["mujoco"] == "3.12.0" and c["runner"] == "lab-1"
    art = client.get("/v1/campaigns/C-0001/artifacts/modes/0/replay.json", headers=u)
    assert art.status_code == 200 and art.json()["format"] == "teeter-replay/1"

    actions = [e["action"] for e in client.get("/v1/audit", headers=u).json()["events"]]
    for a in ("campaign.create", "runner.register", "job.claim", "campaign.complete"):
        assert a in actions


def test_completion_is_refused_until_every_evaluation_has_arrived(client, world):
    client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": SPEC})
    register(client, world.runner)
    jid = client.post("/v1/runner/claim", headers=World.h(world.runner), json={"wait_s": 0}).json()["job"]["id"]
    client.post(f"/v1/runner/jobs/{jid}/evaluations", headers=World.h(world.runner),
                json={"evaluations": [evaluation(0)]})
    r = client.post(f"/v1/runner/jobs/{jid}/complete", headers=World.h(world.runner), json={"result": result(6)})
    assert r.status_code == 409 and r.json()["error"]["code"] == "missing_evaluations"


def test_a_mode_cannot_point_at_an_artifact_that_was_never_uploaded(client, world):
    client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": SPEC})
    register(client, world.runner)
    jid = client.post("/v1/runner/claim", headers=World.h(world.runner), json={"wait_s": 0}).json()["job"]["id"]
    client.post(f"/v1/runner/jobs/{jid}/evaluations", headers=World.h(world.runner),
                json={"evaluations": [evaluation(i) for i in range(6)]})
    r = client.post(f"/v1/runner/jobs/{jid}/complete", headers=World.h(world.runner),
                    json={"result": result(6, [mode(7.9, replay="modes/0/replay.json")])})
    assert r.status_code == 409 and r.json()["error"]["code"] == "missing_artifact"


def test_an_evaluation_beyond_the_budget_is_refused(client, world):
    client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": SPEC})
    register(client, world.runner)
    jid = client.post("/v1/runner/claim", headers=World.h(world.runner), json={"wait_s": 0}).json()["job"]["id"]
    r = client.post(f"/v1/runner/jobs/{jid}/evaluations", headers=World.h(world.runner),
                    json={"evaluations": [evaluation(6)]})
    assert r.status_code == 422


def test_artifact_names_cannot_climb_out_of_their_folder(client, world):
    client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": SPEC})
    register(client, world.runner)
    jid = client.post("/v1/runner/claim", headers=World.h(world.runner), json={"wait_s": 0}).json()["job"]["id"]
    for bad in ("../../etc/passwd", "a/../../b", ".hidden"):
        r = client.put(f"/v1/runner/jobs/{jid}/artifacts/{bad}", headers=World.h(world.runner), content=b"x")
        assert r.status_code in (404, 422), (bad, r.status_code)


def test_the_spec_is_validated_with_readable_messages(client, world):
    u = World.h(world.user)
    bad = [
        ({**SPEC, "axes": {"push_impulse_ns": [9, 0]}}, "upper bound must exceed the lower"),
        ({**SPEC, "axes": {"gravity": [0, 1]}}, "axes.gravity"),
        ({**SPEC, "predicates": [{**SPEC["predicates"][0], "signal": "speed"}]}, "signal"),
        ({**SPEC, "robto": "x"}, "robto"),
        ({**SPEC, "robot": "../../etc/passwd"}, "must be lowercase"),
        ({**SPEC, "search": {"target": "nope"}}, "not a predicate"),
    ]
    for spec, needle in bad:
        r = client.post("/v1/campaigns", headers=u, json={"spec": spec})
        assert r.status_code == 422, (spec, r.text)
        assert needle in r.json()["error"]["message"], (needle, r.json())


def test_cancel_a_queued_campaign_and_a_running_one(client, world):
    u, r = World.h(world.user), World.h(world.runner)
    client.post("/v1/campaigns", headers=u, json={"spec": SPEC})
    client.post("/v1/campaigns", headers=u, json={"spec": SPEC})
    assert client.post("/v1/campaigns/C-0001/cancel", headers=u).json()["state"] == "canceled"

    register(client, world.runner)
    job = client.post("/v1/runner/claim", headers=r, json={"wait_s": 0}).json()
    assert job["campaign"]["ref"] == "C-0002", "a canceled campaign must never be handed out"
    client.post("/v1/campaigns/C-0002/cancel", headers=u)
    hb = client.post(f"/v1/runner/jobs/{job['job']['id']}/heartbeat", headers=r, json={}).json()
    assert hb["cancel"] is True
    client.post(f"/v1/runner/jobs/{job['job']['id']}/fail", headers=r, json={"error": "canceled", "canceled": True})
    assert client.get("/v1/campaigns/C-0002", headers=u).json()["state"] == "canceled"
