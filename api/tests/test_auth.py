"""Who may do what."""

from __future__ import annotations

from conftest import SPEC, World, register


def test_no_token_and_a_wrong_token_are_both_refused(client, world):
    assert client.get("/v1/campaigns").status_code == 401
    r = client.get("/v1/campaigns", headers=World.h("tt_usr_nope"))
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthenticated"


def test_a_runner_token_runs_jobs_and_nothing_else(client, world):
    r = World.h(world.runner)
    assert client.post("/v1/campaigns", headers=r, json={"spec": SPEC}).status_code == 403
    assert client.get("/v1/audit", headers=r).status_code == 403


def test_a_ci_token_cannot_claim_or_administer(client, world):
    ci = World.h(world.ci)
    assert client.post("/v1/campaigns", headers=ci, json={"spec": SPEC}).status_code == 201
    assert client.post("/v1/runner/claim", headers=ci, json={"wait_s": 0}).status_code == 403
    assert client.post("/v1/tokens", headers=ci, json={"name": "x"}).status_code == 403


def test_a_revoked_token_stops_working(client, world):
    u = World.h(world.user)
    made = client.post("/v1/tokens", headers=u, json={"name": "lab-3", "kind": "runner"}).json()
    assert made["secret"].startswith("tt_run_") and "teeter runner start" in made["install"][1]
    register(client, made["secret"], name="lab-3")
    client.delete(f"/v1/tokens/{made['id']}", headers=u)
    assert client.post("/v1/runner/claim", headers=World.h(made["secret"]), json={"wait_s": 0}).status_code == 401
    listed = client.get("/v1/tokens", headers=u).json()["tokens"]
    assert not any(made["secret"] in str(t) for t in listed), "a secret must never be listed"


def test_another_workspaces_campaign_is_invisible(client, world, db):
    from teeter_api.models import Membership, User, Workspace
    from teeter_api.security import mint
    client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": SPEC})
    with db.scope() as s:
        other = Workspace(slug="other", name="Other (example)")
        them = User(email="them@example.com")
        s.add_all([other, them])
        s.flush()
        s.add(Membership(workspace_id=other.id, user_id=them.id, role="owner"))
        _, tok = mint(s, other, "user", "them", user=them)
        s.commit()
    assert client.get("/v1/campaigns/C-0001", headers=World.h(tok)).status_code == 404
    assert client.get("/v1/campaigns", headers=World.h(tok)).json()["campaigns"] == []


def test_a_sign_in_link_works_once_and_keeps_the_token_out_of_logs(client, world, db):
    from datetime import timedelta
    from teeter_api.db import utcnow
    from teeter_api.models import SignInLink, User
    from teeter_api.security import digest
    from sqlalchemy import select
    with db.scope() as s:
        user = s.scalar(select(User))
        s.add(SignInLink(code_sha256=digest("code123"), workspace_id=world.workspace_id, user_id=user.id,
                         expires_at=utcnow() + timedelta(minutes=5)))
        s.commit()
    first = client.get("/v1/auth/link/code123", follow_redirects=False)
    assert first.status_code == 303
    loc = first.headers["location"]
    assert loc.startswith("/app/#/auth/tt_usr_"), "the token rides in the fragment, which no server sees"
    token = loc.split("/auth/", 1)[1]
    assert client.get("/v1/me", headers=World.h(token)).json()["user"]["email"] == "owner@example.com"
    assert client.get("/v1/auth/link/code123", follow_redirects=False).status_code == 410
