"""The workspace: who is signed in, the overview, runners, tokens, the audit log."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import utcnow
from ..errors import ApiError, not_found
from ..models import AuditEvent, Campaign, Gate, Runner, Token
from ..security import Principal, get_session, mint, people, people_or_ci
from ..serialize import iso, online_cutoff, ref, runner_out, token_out

router = APIRouter(prefix="/v1")


@router.get("/me")
def me(p: Principal = Depends(people_or_ci)) -> dict:
    return {"workspace": {"id": p.workspace.id, "slug": p.workspace.slug, "name": p.workspace.name},
            "token": {"kind": p.kind, "prefix": p.token.prefix + "…", "name": p.token.name},
            "user": {"email": p.user.email, "name": p.user.name} if p.user else None}


@router.get("/overview")
def overview(p: Principal = Depends(people_or_ci), session: Session = Depends(get_session)) -> dict:
    ws = p.workspace.id
    by_state = dict(session.execute(select(Campaign.state, func.count()).where(Campaign.workspace_id == ws)
                                    .group_by(Campaign.state)).all())
    runners_all = session.scalars(select(Runner).where(Runner.workspace_id == ws)).all()
    online = [r for r in runners_all if r.last_seen_at >= online_cutoff()]
    gates = dict(session.execute(select(Gate.verdict, func.count()).where(Gate.workspace_id == ws)
                                 .group_by(Gate.verdict)).all())
    return {"campaigns": {k: int(v) for k, v in by_state.items()},
            "runners": {"total": len(runners_all), "online": len(online)},
            "gates": {(k or "waiting"): int(v) for k, v in gates.items()}}


@router.get("/runners")
def list_runners(p: Principal = Depends(people_or_ci), session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(select(Runner).where(Runner.workspace_id == p.workspace.id)
                           .order_by(Runner.last_seen_at.desc())).all()
    return {"runners": [runner_out(r) for r in rows]}


class NewToken(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field("runner", pattern="^(runner|ci|user)$")


@router.post("/tokens", status_code=201)
def create_token(body: NewToken, request: Request, p: Principal = Depends(people),
                 session: Session = Depends(get_session)) -> dict:
    """Shown once. A runner token lets a machine run this workspace's jobs and
    nothing else; a CI token creates campaigns and gates."""
    tok, secret = mint(session, p.workspace, body.kind, body.name, user=p.user if body.kind == "user" else None)
    audit.record(session, p, "token.create", tok.prefix, {"kind": body.kind, "name": body.name}, request)
    session.commit()
    api = str(request.base_url).rstrip("/")
    out = {**token_out(tok), "secret": secret}
    if body.kind == "runner":
        out["install"] = [
            "pip install -e harness -e runner   # from a checkout; a package in M1",
            f"teeter runner start --api {api} --token {secret} --name <machine name>",
        ]
    return out


@router.get("/tokens")
def list_tokens(p: Principal = Depends(people), session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(select(Token).where(Token.workspace_id == p.workspace.id)
                           .order_by(Token.created_at.desc())).all()
    return {"tokens": [token_out(t) for t in rows]}


@router.delete("/tokens/{token_id}")
def revoke_token(token_id: str, request: Request, p: Principal = Depends(people),
                 session: Session = Depends(get_session)) -> dict:
    tok = session.get(Token, token_id)
    if tok is None or tok.workspace_id != p.workspace.id:
        raise not_found("token")
    if tok.id == p.token.id:
        raise ApiError(409, "self_revoke", "this is the token making the request; sign in with another first")
    tok.revoked_at = utcnow()
    audit.record(session, p, "token.revoke", tok.prefix, {"kind": tok.kind, "name": tok.name}, request)
    session.commit()
    return token_out(tok)


@router.get("/audit")
def audit_log(limit: int = 100, p: Principal = Depends(people), session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(select(AuditEvent).where(AuditEvent.workspace_id == p.workspace.id)
                           .order_by(AuditEvent.id.desc()).limit(max(1, min(limit, 500)))).all()
    return {"events": [{"at": iso(e.at), "actor": e.actor, "action": e.action, "target": e.target,
                        "detail": e.detail, "ip": e.ip} for e in rows]}


def campaign_ref(c: Campaign) -> str:
    return ref("C", c.number)
