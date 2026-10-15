"""Bearer tokens, scoped to one workspace.

    tt_usr_…   a person, through the app or the CLI, with their role in the workspace
    tt_ci_…    a CI job: create campaigns and gates, read results
    tt_run_…   a runner: claim jobs, stream results, nothing else
    tt_demo_…  a visitor to the demo workspace: read-only, for twelve hours

Only the SHA-256 of a token is stored. A leaked database cannot be replayed
against the API, and a token is shown exactly once, when it is made.

A demo visit is not stored at all: its token is signed with the server's
secret (TEETER_SECRET) and carries its own workspace and expiry, so anyone may
start one without adding a row anywhere.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import utcnow
from .errors import ApiError
from .models import WRITERS, Membership, Runner, Token, User, Workspace

PREFIX = {"user": "tt_usr_", "ci": "tt_ci_", "runner": "tt_run_"}
DEMO_PREFIX = "tt_demo_"
DEMO_HOURS = 12


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def mint(session: Session, workspace: Workspace, kind: str, name: str,
         user: User | None = None, expires_at: datetime | None = None) -> tuple[Token, str]:
    """A new token. Returns the row and the secret; the secret is not kept."""
    secret = PREFIX[kind] + secrets.token_urlsafe(32)
    tok = Token(workspace_id=workspace.id, kind=kind, name=name, user_id=user.id if user else None,
                prefix=secret[: len(PREFIX[kind]) + 6], secret_sha256=digest(secret), expires_at=expires_at)
    session.add(tok)
    session.flush()
    return tok, secret


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def demo_token(server_secret: str, workspace: Workspace, *, now: float | None = None) -> tuple[str, int]:
    """A signed, read-only pass to one workspace. Returns it and its expiry
    (unix seconds)."""
    exp = int((now or time.time()) + DEMO_HOURS * 3600)
    payload = _b64(json.dumps({"w": workspace.id, "e": exp}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(server_secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{DEMO_PREFIX}{payload}.{sig}", exp


def read_demo_token(server_secret: str, token: str) -> str | None:
    """The workspace id a demo token grants, or None if it is forged or lapsed."""
    if not server_secret or not token.startswith(DEMO_PREFIX):
        return None
    payload, _, sig = token[len(DEMO_PREFIX):].partition(".")
    want = _b64(hmac.new(server_secret.encode(), payload.encode(), hashlib.sha256).digest())
    if not sig or not hmac.compare_digest(sig, want):
        return None
    try:
        claims = json.loads(_unb64(payload))
    except ValueError:
        return None
    return claims["w"] if claims.get("e", 0) > time.time() else None


@dataclass
class Principal:
    token: Token
    workspace: Workspace
    user: User | None
    runner: Runner | None
    role: str = ""             # a person's role in the workspace; "ci" or "runner" for machines

    @property
    def kind(self) -> str:
        return self.token.kind

    @property
    def can_write(self) -> bool:
        return self.kind == "ci" or self.role in WRITERS

    @property
    def actor(self) -> str:
        who = self.user.email if self.user else (f"runner {self.runner.name}" if self.runner else self.token.name)
        return f"{who} ({self.token.prefix}…)"


def get_session(request: Request):
    yield from request.app.state.db.session()


def _authenticate(request: Request, session: Session) -> Principal:
    header = request.headers.get("authorization", "")
    scheme, _, secret = header.partition(" ")
    if scheme.lower() != "bearer" or not secret.strip():
        raise ApiError(401, "unauthenticated", "send 'Authorization: Bearer <token>'; "
                       "make a token with 'teeter-api token' or sign in through the app")
    secret = secret.strip()
    if secret.startswith(DEMO_PREFIX):
        return _demo_principal(request, session, secret)
    tok = session.scalar(select(Token).where(Token.secret_sha256 == digest(secret)))
    if tok is None or tok.revoked_at is not None:
        raise ApiError(401, "unauthenticated", "this token is not valid, or has been revoked")
    now = utcnow()
    if tok.expires_at is not None and tok.expires_at <= now:
        raise ApiError(401, "unauthenticated", "this token has expired; sign in again")
    if tok.last_used_at is None or now - tok.last_used_at > timedelta(seconds=60):
        tok.last_used_at = now          # throttled: one write a minute per token, not per request
        session.commit()
    ws = session.get(Workspace, tok.workspace_id)
    user = session.get(User, tok.user_id) if tok.user_id else None
    runner = session.scalar(select(Runner).where(Runner.token_id == tok.id)) if tok.kind == "runner" else None
    role = tok.kind
    if tok.kind == "user":
        m = session.get(Membership, (tok.workspace_id, tok.user_id)) if tok.user_id else None
        if m is None:
            raise ApiError(401, "unauthenticated", "this person is no longer a member of the workspace")
        role = m.role
    return Principal(token=tok, workspace=ws, user=user, runner=runner, role=role)


def _demo_principal(request: Request, session: Session, secret: str) -> Principal:
    ws_id = read_demo_token(request.app.state.settings.secret, secret)
    ws = session.get(Workspace, ws_id) if ws_id else None
    if ws is None or ws.slug != request.app.state.settings.demo_workspace:
        raise ApiError(401, "unauthenticated", "this demo visit has expired; start another from the sign-in page")
    # nothing about a visit is stored: the token and the visitor are only in memory
    tok = Token(id="demo", workspace_id=ws.id, kind="user", name="demo visit",
                prefix=DEMO_PREFIX + secret[len(DEMO_PREFIX):len(DEMO_PREFIX) + 6], secret_sha256="")
    visitor = User(id="demo", email="visitor@demo.invalid", name="Demo visitor")
    return Principal(token=tok, workspace=ws, user=visitor, runner=None, role="viewer")


def principal(*kinds: str, write: bool = False):
    """A dependency admitting only the given token kinds, and with ``write``
    only those who may change things: CI, and people who are not viewers."""
    def dep(request: Request, session: Session = Depends(get_session)) -> Principal:
        p = _authenticate(request, session)
        if p.kind not in kinds:
            raise ApiError(403, "forbidden", f"a {p.kind} token cannot do this; it needs a {' or '.join(kinds)} token")
        if write and not p.can_write:
            raise ApiError(403, "read_only", f"a {p.role} can look but not change anything in this workspace")
        return p
    return dep


people = principal("user")                          # any member, viewers included: read
people_or_ci = principal("user", "ci")
editors = principal("user", write=True)             # members who may change things
editors_or_ci = principal("user", "ci", write=True)
runners = principal("runner")
