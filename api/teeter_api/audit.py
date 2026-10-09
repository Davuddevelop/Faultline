"""Every write, recorded: who, what, when, from where."""

from __future__ import annotations

import os
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditEvent
from .security import Principal


def client_ip(request: Request) -> str:
    """Behind Vercel the connection comes from its proxy; Vercel puts the
    caller's address in a header that a caller cannot set. Elsewhere, the
    socket's peer (teeter-api serve trusts forwarded headers only from
    localhost)."""
    if os.environ.get("VERCEL"):
        forwarded = request.headers.get("x-vercel-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else ""


def record(session: Session, who: Principal, action: str, target: str = "",
           detail: dict[str, Any] | None = None, request: Request | None = None) -> None:
    ip = client_ip(request) if request is not None else ""
    session.add(AuditEvent(workspace_id=who.workspace.id, actor=who.actor, action=action,
                           target=target, detail=detail or {}, ip=ip))
