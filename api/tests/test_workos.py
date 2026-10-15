"""Sign-in through WorkOS AuthKit, with WorkOS mocked: only invited, verified
addresses come in, a callback this browser did not start is refused, and the
token lands in the URL fragment with the invited role."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import World
from teeter_api.app import create_app
from teeter_api.models import Membership, Token, User, Workspace
from teeter_api.routes.auth_workos import COOKIE, make_state, read_state
from teeter_api.settings import Settings

SECRET = "w" * 40


class FakeWorkOS:
    """Answers /user_management/authenticate for one code."""

    def __init__(self) -> None:
        self.user = {"id": "user_01", "email": "Ada@Example.com", "email_verified": True,
                     "first_name": "Ada", "last_name": "Lovelace"}
        self.requests: list[dict] = []
        self.status = 200

    def __call__(self, req: httpx.Request) -> httpx.Response:
        assert (req.method, req.url.host, req.url.path) == ("POST", "api.workos.com", "/user_management/authenticate")
        body = json.loads(req.content)
        self.requests.append(body)
        if self.status != 200 or body["code"] != "good-code":
            return httpx.Response(self.status if self.status != 200 else 400, json={"error": "invalid_grant"})
        return httpx.Response(200, json={"user": self.user, "access_token": "x", "refresh_token": "y"})


@pytest.fixture
def workos(db, tmp_path, world):
    fake = FakeWorkOS()
    settings = Settings(database_url="unused", storage="local", storage_dir=str(tmp_path / "s"), site_dir="",
                        public_url="https://teeter.example", secret=SECRET,
                        workos_client_id="client_123", workos_api_key="sk_test_123")
    app = create_app(settings, db)
    app.state.workos_http = httpx.Client(transport=httpx.MockTransport(fake))
    with TestClient(app, base_url="https://teeter.example") as c:
        yield c, fake


def _invite(db, world, email="ada@example.com", role="engineer"):
    with db.scope() as s:
        u = User(email=email)
        s.add(u)
        s.flush()
        s.add(Membership(workspace_id=world.workspace_id, user_id=u.id, role=role))
        s.commit()


def _start(c) -> str:
    """Follow the login redirect; returns the state AuthKit would hand back."""
    r = c.get("/v1/auth/workos/login", follow_redirects=False)
    assert r.status_code == 302
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert (url.netloc, url.path) == ("api.workos.com", "/user_management/authorize")
    assert q["client_id"] == ["client_123"] and q["provider"] == ["authkit"] and q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["https://teeter.example/v1/auth/workos/callback"]
    assert COOKIE in r.cookies
    return q["state"][0]


def test_an_invited_verified_address_signs_in_with_its_role(workos, db, world):
    c, fake = workos
    _invite(db, world, role="viewer")
    state = _start(c)
    r = c.get("/v1/auth/workos/callback", params={"code": "good-code", "state": state}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/app/#/auth/tt_usr_")
    token = r.headers["location"].rsplit("/", 1)[1]
    me = c.get("/v1/me", headers=World.h(token)).json()
    assert (me["user"]["email"], me["role"], me["can_write"]) == ("ada@example.com", "viewer", False)
    assert me["token"]["expires_at"] is not None                     # browser sessions lapse
    assert fake.requests[0]["client_secret"] == "sk_test_123" and fake.requests[0]["grant_type"] == "authorization_code"
    with db.scope() as s:
        u = s.scalar(select(User).where(User.email == "ada@example.com"))
        assert (u.workos_id, u.name) == ("user_01", "Ada Lovelace")


def test_an_address_nobody_invited_is_turned_away(workos):
    c, _ = workos
    state = _start(c)
    r = c.get("/v1/auth/workos/callback", params={"code": "good-code", "state": state})
    assert r.status_code == 403 and "has not been invited" in r.text


def test_an_unverified_address_is_turned_away(workos, db, world):
    c, fake = workos
    _invite(db, world)
    fake.user["email_verified"] = False
    r = c.get("/v1/auth/workos/callback", params={"code": "good-code", "state": _start(c)})
    assert r.status_code == 403 and "not verified" in r.text


def test_a_callback_this_browser_did_not_start_is_refused(workos, db, world):
    c, fake = workos
    _invite(db, world)
    forged = make_state(SECRET, "someone-elses-nonce")
    r = c.get("/v1/auth/workos/callback", params={"code": "good-code", "state": forged})
    assert r.status_code == 400 and fake.requests == []              # WorkOS was never asked
    assert read_state(SECRET, forged, "someone-elses-nonce") is not None
    assert read_state("x" * 40, forged, "someone-elses-nonce") is None   # and a state from another secret is junk


def test_a_bad_code_does_not_sign_in(workos, db, world):
    c, _ = workos
    _invite(db, world)
    r = c.get("/v1/auth/workos/callback", params={"code": "stale-code", "state": _start(c)})
    assert r.status_code == 400 and "did not accept" in r.text
    with db.scope() as s:
        assert s.scalar(select(Token).where(Token.name.like("WorkOS%"))) is None


def test_without_keys_there_is_no_workos(client):
    assert client.get("/v1/auth/workos/login", follow_redirects=False).status_code == 404
    assert client.get("/v1/auth/methods").json()["workos"] is False


# ── members ──────────────────────────────────────────────────────────────

def test_owners_invite_change_and_remove_members(client, world, db):
    owner = World.h(world.user)
    assert client.post("/v1/members", headers=owner, json={"email": "Bo@Example.com", "role": "viewer"}).status_code == 201
    assert client.post("/v1/members", headers=owner, json={"email": "bo@example.com", "role": "engineer"}).json()["role"] == "engineer"
    members = {m["email"]: m["role"] for m in client.get("/v1/members", headers=owner).json()["members"]}
    assert members == {"owner@example.com": "owner", "bo@example.com": "engineer"}
    assert client.delete("/v1/members/bo@example.com", headers=owner).json()["removed"] is True
    assert client.delete("/v1/members/owner@example.com", headers=owner).status_code == 409   # not yourself


def test_engineers_cannot_manage_members(client, world, db):
    from teeter_api.security import mint
    with db.scope() as s:
        ws = s.get(Workspace, world.workspace_id)
        u = User(email="eng@example.com")
        s.add(u)
        s.flush()
        s.add(Membership(workspace_id=ws.id, user_id=u.id, role="engineer"))
        _, tok = mint(s, ws, "user", "eng", user=u)
        s.commit()
    r = client.post("/v1/members", headers=World.h(tok), json={"email": "x@example.com"})
    assert r.status_code == 403
