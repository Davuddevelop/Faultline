"""Sign-in through WorkOS AuthKit, and who may sign in.

    GET  /v1/auth/workos/login       send the browser to AuthKit
    GET  /v1/auth/workos/callback    AuthKit sends it back with a code
    GET  /v1/members                 the workspace's people and roles (owners and admins)
    POST /v1/members                 invite someone, or change their role
    DELETE /v1/members/{email}       remove someone

AuthKit proves who someone is; this server decides whether they may come
in. Only an address that a workspace has invited (POST /v1/members, or
'teeter-api member') is let in, with the role it was given. The first
sign-in ties the WorkOS user id to that invitation.

The OAuth state is signed with TEETER_SECRET and bound to a short-lived
cookie, so a callback that this browser did not start is refused. The token
minted at the end travels in the URL fragment, as with sign-in links.

Configured by WORKOS_CLIENT_ID and WORKOS_API_KEY, plus TEETER_SECRET; the
redirect URI to register in the WorkOS dashboard is
<public url>/v1/auth/workos/callback.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import time
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit
from ..db import utcnow
from ..errors import ApiError, not_found
from ..models import ROLES, Membership, User, Workspace
from ..security import Principal, get_session, mint, principal

router = APIRouter(prefix="/v1")

WORKOS_API = "https://api.workos.com"
COOKIE = "teeter_signin"
SESSION_DAYS = 30
admins = principal("user", write=True)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _sign(secret: str, payload: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def make_state(secret: str, nonce: str, workspace: str = "", *, ttl_s: int = 600) -> str:
    payload = _b64(json.dumps({"n": nonce, "w": workspace, "e": int(time.time()) + ttl_s},
                              separators=(",", ":")).encode())
    return f"{payload}.{_sign(secret, payload)}"


def read_state(secret: str, state: str, nonce: str) -> dict | None:
    payload, _, sig = state.partition(".")
    if not sig or not hmac.compare_digest(sig, _sign(secret, payload)):
        return None
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except ValueError:
        return None
    if claims.get("e", 0) < time.time() or not nonce or not hmac.compare_digest(claims.get("n", ""), nonce):
        return None
    return claims


def _redirect_uri(request: Request) -> str:
    return request.app.state.settings.public_url.rstrip("/") + "/v1/auth/workos/callback"


def _refuse(why: str, status: int = 403) -> HTMLResponse:
    """A sign-in that cannot finish ends on a plain page that says why."""
    body = (f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            f"<title>Sign-in did not finish</title><body style='font:16px/1.5 system-ui;max-width:36rem;"
            f"margin:15vh auto;padding:0 16px;background:#111;color:#e8e6e1'><h1 style='font-size:20px'>"
            f"Sign-in did not finish</h1><p>{html.escape(why)}</p><p><a style='color:#e8e6e1' "
            f"href='/app/#/login'>Back to sign-in</a></p></body>")
    resp = HTMLResponse(body, status_code=status)
    resp.delete_cookie(COOKIE, path="/v1/auth/workos")
    return resp


@router.get("/auth/workos/login")
def workos_login(request: Request, workspace: str = "") -> RedirectResponse:
    settings = request.app.state.settings
    if not settings.workos_enabled:
        raise ApiError(404, "no_workos", "this server signs in with links; WorkOS is not configured")
    nonce = secrets.token_urlsafe(24)
    query = urlencode({"client_id": settings.workos_client_id, "redirect_uri": _redirect_uri(request),
                       "response_type": "code", "provider": "authkit",
                       "state": make_state(settings.secret, nonce, workspace)})
    resp = RedirectResponse(f"{WORKOS_API}/user_management/authorize?{query}", status_code=302)
    resp.set_cookie(COOKIE, nonce, max_age=600, path="/v1/auth/workos", httponly=True,
                    secure=settings.public_url.startswith("https://"), samesite="lax")
    return resp


@router.get("/auth/workos/callback")
def workos_callback(request: Request, code: str = "", state: str = "", error: str = "",
                    error_description: str = "", session: Session = Depends(get_session)):
    settings = request.app.state.settings
    if not settings.workos_enabled:
        raise ApiError(404, "no_workos", "WorkOS is not configured on this server")
    if error:
        return _refuse(f"WorkOS said: {error_description or error}.", 400)
    claims = read_state(settings.secret, state, request.cookies.get(COOKIE, ""))
    if claims is None or not code:
        return _refuse("This sign-in was not started from this browser, or took longer than ten minutes. "
                       "Start again from the sign-in page.", 400)
    try:
        r = request.app.state.workos_http.post(f"{WORKOS_API}/user_management/authenticate", json={
            "client_id": settings.workos_client_id, "client_secret": settings.workos_api_key,
            "grant_type": "authorization_code", "code": code,
            "ip_address": audit.client_ip(request), "user_agent": request.headers.get("user-agent", "")[:500]})
    except httpx.HTTPError:
        return _refuse("WorkOS could not be reached. Try again in a minute.", 502)
    if r.status_code != 200:
        return _refuse("WorkOS did not accept the sign-in code. Start again from the sign-in page.", 400)
    wu = r.json().get("user") or {}
    email = (wu.get("email") or "").strip().lower()
    if not email or not wu.get("email_verified"):
        return _refuse("WorkOS has not verified this address yet. Verify it, then sign in again.")

    user = (session.scalar(select(User).where(User.workos_id == wu.get("id"))) if wu.get("id") else None) \
        or session.scalar(select(User).where(User.email == email))
    memberships = session.scalars(select(Membership).where(Membership.user_id == user.id)).all() if user else []
    if not memberships:
        return _refuse(f"{email} has not been invited to a workspace on this server. Ask an owner to add you "
                       f"(the Members API, or 'teeter-api member --email {email}').")
    want = claims.get("w") or ""
    chosen = None
    for m in memberships:
        ws = session.get(Workspace, m.workspace_id)
        if not want or ws.slug == want:
            chosen = (ws, m)
            break
    if chosen is None:
        return _refuse(f"{email} is not a member of the workspace {want!r}.")
    ws, m = chosen
    if user.workos_id is None and wu.get("id"):
        user.workos_id = wu["id"]
    if not user.name:
        user.name = " ".join(x for x in (wu.get("first_name"), wu.get("last_name")) if x)[:200]
    tok, secret = mint(session, ws, "user", f"WorkOS sign-in, {email}", user=user,
                       expires_at=utcnow() + timedelta(days=SESSION_DAYS))
    audit.record(session, Principal(token=tok, workspace=ws, user=user, runner=None, role=m.role),
                 "auth.signin", email, {"via": "workos", "role": m.role}, request)
    session.commit()
    resp = RedirectResponse(f"/app/#/auth/{secret}", status_code=303)
    resp.delete_cookie(COOKIE, path="/v1/auth/workos")
    return resp


# ── members ──────────────────────────────────────────────────────────────

class Invite(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    role: str = Field("engineer", pattern="^(" + "|".join(ROLES) + ")$")


def _admin(p: Principal) -> None:
    if p.role not in ("owner", "admin"):
        raise ApiError(403, "forbidden", "only owners and admins manage members")


@router.get("/members")
def list_members(p: Principal = Depends(admins), session: Session = Depends(get_session)) -> dict:
    _admin(p)
    rows = session.execute(select(User, Membership).join(Membership, Membership.user_id == User.id)
                           .where(Membership.workspace_id == p.workspace.id).order_by(User.email)).all()
    return {"members": [{"email": u.email, "name": u.name, "role": m.role, "signed_in_with_workos": bool(u.workos_id)}
                        for u, m in rows]}


@router.post("/members", status_code=201)
def invite(body: Invite, request: Request, p: Principal = Depends(admins),
           session: Session = Depends(get_session)) -> dict:
    _admin(p)
    if body.role == "owner" and p.role != "owner":
        raise ApiError(403, "forbidden", "only an owner can make another owner")
    email = body.email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        session.add(user)
        session.flush()
    m = session.get(Membership, (p.workspace.id, user.id))
    if m is None:
        session.add(Membership(workspace_id=p.workspace.id, user_id=user.id, role=body.role))
    else:
        m.role = body.role
    audit.record(session, p, "member.invite", email, {"role": body.role}, request)
    session.commit()
    return {"email": email, "role": body.role}


@router.delete("/members/{email}")
def remove(email: str, request: Request, p: Principal = Depends(admins),
           session: Session = Depends(get_session)) -> dict:
    _admin(p)
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    m = session.get(Membership, (p.workspace.id, user.id)) if user else None
    if m is None:
        raise not_found(f"member {email!r}")
    if user.id == (p.user.id if p.user else None):
        raise ApiError(409, "self_remove", "you cannot remove yourself; ask another owner")
    if m.role == "owner" and p.role != "owner":
        raise ApiError(403, "forbidden", "only an owner can remove an owner")
    session.delete(m)
    audit.record(session, p, "member.remove", user.email, {"role": m.role}, request)
    session.commit()
    return {"email": user.email, "removed": True}
