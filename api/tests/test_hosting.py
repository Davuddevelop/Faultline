"""What the hosted control plane relies on: migrations that build the same
schema the models describe, the private Blob store's wire protocol, the
claim's Retry-After, roles that keep viewers read-only, and demo visits that
are signed rather than stored."""

from __future__ import annotations

import json
import time

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select, text

from conftest import PG, SPEC, World
from teeter_api.app import create_app
from teeter_api.db import Base, Database
from teeter_api.models import Membership, Token, User, Workspace
from teeter_api.security import DEMO_PREFIX, demo_token, mint, read_demo_token
from teeter_api.settings import Settings, normalise_db_url
from teeter_api.storage import BlobError, BlobStorage

SECRET = "s" * 40


# ── migrations ───────────────────────────────────────────────────────────

def _fresh(backend: str, tmp_path) -> Database:
    if backend == "postgres":
        db = Database(PG)
        with db.engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        return db
    return Database(f"sqlite:///{tmp_path / 'm.sqlite'}")


@pytest.mark.parametrize("backend", ["sqlite"] + (["postgres"] if PG else []))
def test_migrations_build_exactly_the_models_schema(backend, tmp_path):
    db = _fresh(backend, tmp_path)
    assert db.revision() is None
    assert db.migrate() == "0001"
    assert db.migrate() == "0001"                     # again: nothing to do, no error
    from teeter_api import models  # noqa: F401
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == [], f"the migrations and models.py disagree: {diff}"
    db.engine.dispose()


def test_a_database_made_before_migrations_is_refused_with_advice(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'old.sqlite'}")
    db.create_all()
    with pytest.raises(RuntimeError, match="no migration history"):
        db.migrate()


def test_provider_urls_are_read_with_psycopg_3():
    assert normalise_db_url("postgres://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert normalise_db_url("postgresql://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalise_db_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalise_db_url("sqlite:///x.db") == "sqlite:///x.db"


def test_database_url_falls_back_to_the_providers_name(monkeypatch):
    monkeypatch.delenv("TEETER_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@pooler.example/db")
    monkeypatch.setenv("DATABASE_URL_UNPOOLED", "postgres://u:p@direct.example/db")
    s = Settings()
    assert s.database_url == "postgresql+psycopg://u:p@pooler.example/db"
    assert s.database_url_direct == "postgresql+psycopg://u:p@direct.example/db"


def test_on_vercel_claims_return_at_once_and_pools_are_small(monkeypatch):
    for k in ("TEETER_CLAIM_WAIT_S", "TEETER_CLAIM_RETRY_S", "TEETER_DB_POOL_SIZE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("VERCEL", "1")
    s = Settings()
    assert (s.claim_wait_max_s, s.claim_retry_s, s.db_pool_size) == (0.0, 10.0, 2)
    monkeypatch.delenv("TEETER_STATE_DIR", raising=False)
    monkeypatch.delenv("TEETER_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings().database_url == "sqlite:////tmp/teeter/dev.sqlite"   # writable on a function
    monkeypatch.delenv("VERCEL")
    s = Settings()
    assert (s.claim_wait_max_s, s.claim_retry_s, s.db_pool_size) == (25.0, 1.0, 10)


# ── Vercel Blob, over its HTTP API ───────────────────────────────────────

TOKEN = "vercel_blob_rw_St0reId_s3cret"


def _blob(handler):
    return BlobStorage(TOKEN, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_blob_put_is_private_and_overwrites_in_place():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"url": "https://st0reid.private.blob.vercel-storage.com/w/c/a.json",
                                         "pathname": "w/c/a.json"})

    sha = _blob(handler).put("w/c/a.json", b'{"x":1}', "application/json")
    r = seen[0]
    assert (r.method, r.url.host, r.url.path, r.url.params["pathname"]) == ("PUT", "vercel.com", "/api/blob", "w/c/a.json")
    assert r.headers["authorization"] == f"Bearer {TOKEN}"
    assert r.headers["x-vercel-blob-access"] == "private"
    assert (r.headers["x-add-random-suffix"], r.headers["x-allow-overwrite"]) == ("0", "1")
    assert r.headers["x-content-type"] == "application/json"
    assert r.content == b'{"x":1}'
    import hashlib
    assert sha == hashlib.sha256(b'{"x":1}').hexdigest()


def test_blob_get_reads_the_private_host_with_the_token():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.host == "St0reId.private.blob.vercel-storage.com".lower()
        assert req.headers["authorization"] == f"Bearer {TOKEN}"
        return httpx.Response(200, content=b"trace") if req.url.path == "/w/c/t.csv" else httpx.Response(404)

    store = _blob(handler)
    assert store.get("w/c/t.csv") == b"trace"
    with pytest.raises(FileNotFoundError):
        store.get("w/c/missing.csv")


def test_blob_delete_prefix_pages_through_the_listing():
    deleted = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            page = req.url.params.get("cursor")
            assert req.url.params["prefix"] == "w/c/"
            if page is None:
                return httpx.Response(200, json={"blobs": [{"url": "u1"}, {"url": "u2"}], "cursor": "p2", "hasMore": True})
            return httpx.Response(200, json={"blobs": [{"url": "u3"}], "hasMore": False})
        assert req.url.path == "/api/blob/delete"
        deleted.extend(json.loads(req.content)["urls"])
        return httpx.Response(200)

    _blob(handler).delete_prefix("w/c")
    assert deleted == ["u1", "u2", "u3"]


def test_blob_errors_say_what_failed():
    store = _blob(lambda req: httpx.Response(403, json={"error": {"code": "forbidden", "message": "no"}}))
    with pytest.raises(BlobError, match="put k: 403 forbidden no"):
        store.put("k", b"1")
    with pytest.raises(BlobError, match="read-write token"):
        BlobStorage("not-a-token")


# ── claims ───────────────────────────────────────────────────────────────

def test_an_empty_claim_says_when_to_ask_again(db, tmp_path, world):
    from conftest import register
    settings = Settings(database_url="unused", storage="local", storage_dir=str(tmp_path / "s"), site_dir="",
                        public_url="http://testserver", claim_wait_max_s=0.0, claim_retry_s=10.0)
    from fastapi.testclient import TestClient
    with TestClient(create_app(settings, db)) as c:
        register(c, world.runner)
        t0 = time.monotonic()
        r = c.post("/v1/runner/claim", headers=World.h(world.runner), json={"wait_s": 20})
        assert r.status_code == 204 and r.headers["retry-after"] == "10"
        assert time.monotonic() - t0 < 2, "a serverless claim must not wait"


# ── roles ────────────────────────────────────────────────────────────────

def _member(db, world, role: str) -> str:
    with db.scope() as s:
        ws = s.get(Workspace, world.workspace_id)
        u = User(email=f"{role}@example.com")
        s.add(u)
        s.flush()
        s.add(Membership(workspace_id=ws.id, user_id=u.id, role=role))
        _, tok = mint(s, ws, "user", role, user=u)
        s.commit()
    return tok


def test_a_viewer_reads_but_cannot_change_anything(client, world, db):
    viewer = World.h(_member(db, world, "viewer"))
    assert client.post("/v1/campaigns", headers=World.h(world.user), json={"spec": SPEC}).status_code == 201
    assert client.get("/v1/campaigns/C-0001", headers=viewer).status_code == 200
    me = client.get("/v1/me", headers=viewer).json()
    assert (me["role"], me["can_write"]) == ("viewer", False)
    for method, path, body in (("POST", "/v1/campaigns", {"spec": SPEC}), ("POST", "/v1/campaigns/C-0001/cancel", {}),
                               ("POST", "/v1/tokens", {"name": "x"}), ("GET", "/v1/tokens", None),
                               ("GET", "/v1/audit", None),
                               ("POST", "/v1/programs", {"slug": "p", "name": "P", "standard_spec": {}})):
        r = client.request(method, path, headers=viewer, json=body)
        assert r.status_code == 403 and r.json()["error"]["code"] == "read_only", (method, path, r.text)


def test_an_engineer_may_plan_campaigns(client, world, db):
    eng = World.h(_member(db, world, "engineer"))
    assert client.post("/v1/campaigns", headers=eng, json={"spec": SPEC}).status_code == 201


def test_a_removed_member_is_signed_out(client, world, db):
    tok = _member(db, world, "engineer")
    with db.scope() as s:
        u = s.scalar(select(User).where(User.email == "engineer@example.com"))
        s.delete(s.get(Membership, (world.workspace_id, u.id)))
        s.commit()
    r = client.get("/v1/me", headers=World.h(tok))
    assert r.status_code == 401 and "no longer a member" in r.json()["error"]["message"]


def test_an_expired_token_is_refused(client, world, db):
    from datetime import timedelta

    from teeter_api.db import utcnow
    with db.scope() as s:
        tok = s.scalar(select(Token).where(Token.kind == "user"))
        tok.expires_at = utcnow() - timedelta(seconds=1)
        s.commit()
    assert client.get("/v1/me", headers=World.h(world.user)).status_code == 401


# ── demo visits ──────────────────────────────────────────────────────────

@pytest.fixture
def demo_client(db, tmp_path, world):
    from fastapi.testclient import TestClient
    with db.scope() as s:
        s.get(Workspace, world.workspace_id).slug = "demo"
        s.commit()
    settings = Settings(database_url="unused", storage="local", storage_dir=str(tmp_path / "s"), site_dir="",
                        public_url="http://testserver", demo_workspace="demo", secret=SECRET)
    with TestClient(create_app(settings, db)) as c:
        yield c


def test_a_demo_visit_is_read_only_and_leaves_no_rows(demo_client, world, db):
    with db.scope() as s:
        before = s.scalar(select(func.count()).select_from(Token))
    assert demo_client.get("/v1/auth/methods").json()["demo"] == {"workspace": "Acme (example)"}
    visit = demo_client.post("/v1/auth/demo").json()
    assert visit["token"].startswith(DEMO_PREFIX) and visit["role"] == "viewer"
    h = World.h(visit["token"])
    me = demo_client.get("/v1/me", headers=h).json()
    assert (me["role"], me["can_write"], me["workspace"]["slug"]) == ("viewer", False, "demo")
    assert demo_client.get("/v1/campaigns", headers=h).status_code == 200
    assert demo_client.post("/v1/campaigns", headers=h, json={"spec": SPEC}).status_code == 403
    assert demo_client.get("/v1/audit", headers=h).status_code == 403          # addresses stay private
    with db.scope() as s:
        assert s.scalar(select(func.count()).select_from(Token)) == before


def test_demo_tokens_cannot_be_forged_or_kept(demo_client, world, db):
    with db.scope() as s:
        ws = s.get(Workspace, world.workspace_id)
        good, _ = demo_token(SECRET, ws)
        forged, _ = demo_token("x" * 40, ws)
        stale, _ = demo_token(SECRET, ws, now=time.time() - 13 * 3600)
    assert read_demo_token(SECRET, good) == world.workspace_id
    for bad in (forged, stale, good[:-2] + "AA", DEMO_PREFIX + "garbage"):
        assert read_demo_token(SECRET, bad) is None
        assert demo_client.get("/v1/me", headers=World.h(bad)).status_code == 401


def test_without_a_secret_or_workspace_there_are_no_demo_visits(client):
    assert client.get("/v1/auth/methods").json() == {"link": True, "workos": False, "demo": None}
    assert client.post("/v1/auth/demo").status_code == 404
