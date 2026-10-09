"""Bearer tokens, scoped to one workspace.

    tt_usr_…   a person, through the app or the CLI
    tt_ci_…    a CI job: create campaigns and gates, read results
    tt_run_…   a runner: claim jobs, stream results, nothing else

Only the SHA-256 of a token is stored. A leaked database cannot be replayed
against the API, and a token is shown exactly once, when it is made.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import utcnow
from .errors import ApiError
from .models import Runner, Token, User, Workspace

PREFIX = {"user": "tt_usr_", "ci": "tt_ci_", "runner": "tt_run_"}


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def mint(session: Session, workspace: Workspace, kind: str, name: str,
         user: User | None = None) -> tuple[Token, str]:
    """A new token. Returns the row and the secret; the secret is not kept."""
    secret = PREFIX[kind] + secrets.token_urlsafe(32)
    tok = Token(workspace_id=workspace.id, kind=kind, name=name, user_id=user.id if user else None,
                prefix=secret[: len(PREFIX[kind]) + 6], secret_sha256=digest(secret))
    session.add(tok)
    session.flush()
    return tok, secret


@dataclass
class Principal:
    token: Token
    workspace: Workspace
    user: User | None
    runner: Runner | None

    @property
    def kind(self) -> str:
        return self.token.kind

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
    tok = session.scalar(select(Token).where(Token.secret_sha256 == digest(secret.strip())))
    if tok is None or tok.revoked_at is not None:
        raise ApiError(401, "unauthenticated", "this token is not valid, or has been revoked")
    now = utcnow()
    if tok.last_used_at is None or now - tok.last_used_at > timedelta(seconds=60):
        tok.last_used_at = now          # throttled: one write a minute per token, not per request
        session.commit()
    ws = session.get(Workspace, tok.workspace_id)
    user = session.get(User, tok.user_id) if tok.user_id else None
    runner = session.scalar(select(Runner).where(Runner.token_id == tok.id)) if tok.kind == "runner" else None
    return Principal(token=tok, workspace=ws, user=user, runner=runner)


def principal(*kinds: str):
    """A dependency admitting only the given token kinds."""
    def dep(request: Request, session: Session = Depends(get_session)) -> Principal:
        p = _authenticate(request, session)
        if p.kind not in kinds:
            raise ApiError(403, "forbidden", f"a {p.kind} token cannot do this; it needs a {' or '.join(kinds)} token")
        return p
    return dep


people = principal("user")
people_or_ci = principal("user", "ci")
runners = principal("runner")
