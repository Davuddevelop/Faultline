"""Campaigns: plan one, watch it run, read what it found."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, queue, service
from ..contracts import CampaignSpec
from ..errors import ApiError, not_found
from ..models import Artifact, Campaign, Evaluation, Job
from ..security import Principal, get_session, people, people_or_ci

router = APIRouter(prefix="/v1")


class NewCampaign(BaseModel):
    spec: CampaignSpec


@router.post("/campaigns", status_code=201)
def create(body: NewCampaign, request: Request, p: Principal = Depends(people_or_ci),
           session: Session = Depends(get_session)) -> dict:
    settings = request.app.state.settings
    c = service.create_campaign(session, p, body.spec, max_attempts=settings.max_attempts, request=request)
    return service.campaign_detail(session, c)


@router.get("/campaigns")
def list_campaigns(limit: int = 50, state: str | None = None, p: Principal = Depends(people_or_ci),
                   session: Session = Depends(get_session)) -> dict:
    q = select(Campaign).where(Campaign.workspace_id == p.workspace.id)
    if state:
        q = q.where(Campaign.state == state)
    rows = session.scalars(q.order_by(Campaign.number.desc()).limit(max(1, min(limit, 200)))).all()
    return {"campaigns": [service.campaign_detail(session, c, detail=False) for c in rows]}


@router.get("/campaigns/{ref}")
def get_campaign(ref: str, p: Principal = Depends(people_or_ci), session: Session = Depends(get_session)) -> dict:
    return service.campaign_detail(session, service.find_campaign(session, p.workspace.id, ref))


@router.get("/campaigns/{ref}/evaluations")
def evaluations(ref: str, after: int = -1, limit: int = 1000, p: Principal = Depends(people_or_ci),
                session: Session = Depends(get_session)) -> dict:
    """Evaluations after an index, in index order. Poll with the returned
    ``next_after`` to follow a running campaign without re-reading it."""
    c = service.find_campaign(session, p.workspace.id, ref)
    rows = session.scalars(select(Evaluation).where(Evaluation.campaign_id == c.id, Evaluation.index > after)
                           .order_by(Evaluation.index).limit(max(1, min(limit, 5000)))).all()
    return {
        "campaign": c.id, "ref": f"C-{c.number:04d}", "state": c.state, "progress": c.progress or {},
        "budget": c.spec["search"]["budget"], "evaluations_total": c.n_evaluations,
        "failures_total": c.n_failures, "first_failure_index": c.first_failure_index,
        "next_after": rows[-1].index if rows else after,
        "evaluations": [{"index": e.index, "iteration": e.iteration, "perturbation": e.perturbation,
                         "severity": e.severity, "failed": e.failed, "invalid": e.invalid,
                         "violation": e.violation} for e in rows],
    }


@router.get("/campaigns/{ref}/artifacts/{name:path}")
def artifact(ref: str, name: str, request: Request, p: Principal = Depends(people_or_ci),
             session: Session = Depends(get_session)) -> Response:
    c = service.find_campaign(session, p.workspace.id, ref)
    a = session.scalar(select(Artifact).where(Artifact.campaign_id == c.id, Artifact.name == name))
    if a is None:
        raise not_found(f"artifact {name!r}")
    data = request.app.state.storage.get(a.storage_key)
    return Response(data, media_type=a.content_type,
                    headers={"Cache-Control": "private, max-age=3600", "X-Content-SHA256": a.sha256})


@router.post("/campaigns/{ref}/cancel")
def cancel(ref: str, request: Request, p: Principal = Depends(people),
           session: Session = Depends(get_session)) -> dict:
    c = service.find_campaign(session, p.workspace.id, ref)
    if c.state in ("done", "failed", "canceled"):
        raise ApiError(409, "finished", f"C-{c.number:04d} has already {c.state}")
    job = session.scalar(select(Job).where(Job.campaign_id == c.id))
    if job and job.state == "queued":
        queue.finish(session, job, "canceled", error="canceled before a runner took it")
        service.decide_gates_for(session, c)
    else:
        c.cancel_requested = True              # the runner sees it on its next heartbeat
    audit.record(session, p, "campaign.cancel", f"C-{c.number:04d}", {}, request)
    session.commit()
    return service.campaign_detail(session, c)
