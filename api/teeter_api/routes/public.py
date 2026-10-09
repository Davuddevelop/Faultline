"""What answers without a token: health, and following a sign-in link."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import __version__
from ..contracts import AXES, SIGNALS, SPEC_VERSION
from ..db import utcnow
from ..errors import ApiError
from ..models import SignInLink, User, Workspace
from ..security import digest, get_session, mint

router = APIRouter(prefix="/v1")


@router.get("/health")
def health(request: Request) -> dict:
    return {"ok": True, "service": "teeter-api", "version": __version__,
            "database": request.app.state.db.engine.dialect.name, "spec": SPEC_VERSION}


@router.get("/contracts")
def contracts() -> dict:
    """The axis table and signal list this server validates against, so a
    client can build a form without restating them."""
    return {"spec": SPEC_VERSION, "signals": list(SIGNALS),
            "axes": [{"name": k, "unit": u, "nominal": n, "tolerance": t, "requested_value": q}
                     for k, (u, n, t, q) in AXES.items()]}


@router.get("/auth/link/{code}")
def follow_link(code: str, session: Session = Depends(get_session)) -> RedirectResponse:
    """Sign a browser in. The new token travels in the URL fragment, which
    browsers never send to a server, so it reaches no access log."""
    link = session.scalar(select(SignInLink).where(SignInLink.code_sha256 == digest(code)))
    if link is None or link.used_at is not None or link.expires_at < utcnow():
        raise ApiError(410, "link_used", "this sign-in link has been used or has expired; "
                       "ask for a new one with 'teeter-api link'")
    link.used_at = utcnow()
    ws, user = session.get(Workspace, link.workspace_id), session.get(User, link.user_id)
    _, secret = mint(session, ws, "user", f"browser sign-in, {user.email}", user=user)
    session.commit()
    return RedirectResponse(f"/app/#/auth/{secret}", status_code=303)
