"""Every write, recorded: who, what, when, from where."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditEvent
from .security import Principal


def record(session: Session, who: Principal, action: str, target: str = "",
           detail: dict[str, Any] | None = None, request: Request | None = None) -> None:
    ip = request.client.host if request is not None and request.client else ""
    session.add(AuditEvent(workspace_id=who.workspace.id, actor=who.actor, action=action,
                           target=target, detail=detail or {}, ip=ip))
