"""The runner protocol, v1. Every call is made by the runner, outbound.

    POST /v1/runner/register                    who I am, what I allow
    POST /v1/runner/claim                       long-poll for a job
    POST /v1/runner/jobs/{id}/heartbeat         renew my lease; is it canceled?
    POST /v1/runner/jobs/{id}/evaluations       results so far, any order, idempotent
    PUT  /v1/runner/jobs/{id}/artifacts/{name}  a replay or a trace
    POST /v1/runner/jobs/{id}/complete          the result
    POST /v1/runner/jobs/{id}/fail              why it could not finish

A runner that has lost its lease (it stalled, and another runner took the
job) gets 409 on every job call and must drop the job.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import audit, queue, service
from ..contracts import EvaluationIn, ResultIn
from ..db import utcnow
from ..errors import ApiError
from ..models import Artifact, Campaign, FailureMode, Job, Runner
from ..security import Principal, _authenticate, get_session, runners
from ..serialize import iso, runner_out
from ..storage import MAX_BYTES, valid_name

router = APIRouter(prefix="/v1/runner")


class Register(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,99}$")
    host: dict[str, Any] = Field(default_factory=dict)
    versions: dict[str, Any] = Field(default_factory=dict)
    cores: int = Field(1, ge=1, le=4096)
    robots: list[str] = Field(default_factory=list, max_length=200)
    policies: list[str] = Field(default_factory=list, max_length=200)


@router.post("/register")
def register(body: Register, request: Request, session: Session = Depends(get_session)) -> dict:
    p = _authenticate(request, session)
    if p.kind != "runner":
        raise ApiError(403, "forbidden", "register with a runner token (tt_run_…), made on the Runners page")
    r = p.runner or session.scalar(select(Runner).where(Runner.workspace_id == p.workspace.id,
                                                        Runner.name == body.name))
    if r is None:
        r = Runner(workspace_id=p.workspace.id, token_id=p.token.id, name=body.name)
        session.add(r)
    elif r.token_id != p.token.id:
        raise ApiError(409, "name_taken", f"a runner called {body.name!r} is registered with another token")
    r.name, r.host, r.versions, r.cores = body.name, body.host, body.versions, body.cores
    r.robots, r.policies, r.last_seen_at = sorted(set(body.robots)), sorted(set(body.policies)), utcnow()
    p.runner = r
    audit.record(session, p, "runner.register", body.name,
                 {"robots": r.robots, "policies": r.policies, "versions": body.versions}, request)
    session.commit()
    return runner_out(r)


class Claim(BaseModel):
    wait_s: float = Field(20.0, ge=0.0, le=60.0)


def _job_out(session: Session, job: Job, settings) -> dict:
    c = session.get(Campaign, job.campaign_id)
    return {"job": {"id": job.id, "attempt": job.attempts, "lease_s": settings.lease_s,
                    "lease_expires_at": iso(job.lease_expires_at)},
            "campaign": {"id": c.id, "ref": f"C-{c.number:04d}", "spec": c.spec}}


@router.post("/claim")
async def claim(body: Claim, request: Request) -> Response:
    """Wait up to ``wait_s`` for a job (at most TEETER_CLAIM_WAIT_S). Async, so
    a waiting runner holds no thread; each try is one indexed query. Empty
    handed, the answer is 204 with Retry-After."""
    app = request.app
    settings, db = app.state.settings, app.state.db

    def attempt() -> dict | None:
        with db.scope() as session:
            p = _authenticate(request, session)
            if p.kind != "runner" or p.runner is None:
                raise ApiError(403, "forbidden", "claim with a registered runner's token; call /register first")
            p.runner.last_seen_at = utcnow()
            session.commit()
            job = queue.claim(session, p.runner, settings.lease_s, is_postgres=db.is_postgres)
            if job is None:
                return None
            c = session.get(Campaign, job.campaign_id)
            audit.record(session, p, "job.claim", f"C-{c.number:04d}", {"attempt": job.attempts})
            session.commit()
            return _job_out(session, job, settings)

    deadline = time.monotonic() + min(body.wait_s, settings.claim_wait_max_s)
    while True:
        got = await run_in_threadpool(attempt)
        if got is not None:
            return Response(json.dumps(got), media_type="application/json")
        if time.monotonic() >= deadline or await request.is_disconnected():
            # no work: when to ask again. A long-polling server has already
            # waited, so soon; a serverless one returned at once, so later.
            return Response(status_code=204, headers={"Retry-After": f"{settings.claim_retry_s:g}"})
        await asyncio.sleep(1.0)


def _held(session: Session, p: Principal, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.workspace_id != p.workspace.id:
        raise ApiError(404, "not_found", "no such job")
    if p.runner is None or not queue.holds(job, p.runner):
        raise ApiError(409, "lease_lost", "this runner no longer holds the job (its lease lapsed, "
                       "or the campaign was canceled); drop it and claim again")
    return job


class Heartbeat(BaseModel):
    progress: dict[str, Any] = Field(default_factory=dict)


@router.post("/jobs/{job_id}/heartbeat")
def heartbeat(job_id: str, body: Heartbeat, request: Request, p: Principal = Depends(runners),
              session: Session = Depends(get_session)) -> dict:
    job = _held(session, p, job_id)
    held, cancel = queue.renew(session, job, p.runner, request.app.state.settings.lease_s, body.progress)
    if not held:
        raise ApiError(409, "lease_lost", "this runner no longer holds the job; drop it")
    return {"held": True, "cancel": cancel, "lease_expires_at": iso(job.lease_expires_at)}


class Evaluations(BaseModel):
    evaluations: list[EvaluationIn] = Field(max_length=5000)


@router.post("/jobs/{job_id}/evaluations")
def post_evaluations(job_id: str, body: Evaluations, request: Request, p: Principal = Depends(runners),
                     session: Session = Depends(get_session)) -> dict:
    job = _held(session, p, job_id)
    c = session.get(Campaign, job.campaign_id)
    budget = c.spec["search"]["budget"]
    if any(e.index >= budget for e in body.evaluations):
        raise ApiError(422, "out_of_budget", f"an evaluation index is beyond this campaign's budget of {budget}")
    new = queue.ingest(session, c, body.evaluations, is_postgres=request.app.state.db.is_postgres)
    session.refresh(c)
    return {"accepted": new, "evaluations_total": c.n_evaluations, "failures_total": c.n_failures}


@router.put("/jobs/{job_id}/artifacts/{name:path}", status_code=201)
async def put_artifact(job_id: str, name: str, request: Request) -> dict:
    if not valid_name(name):
        raise ApiError(422, "bad_name", "artifact names are relative paths of letters, digits, '.', '_' and '-'")
    data = await request.body()
    if len(data) > MAX_BYTES:
        raise ApiError(413, "too_large", f"artifacts are limited to {MAX_BYTES // (1024 * 1024)} MB")
    ctype = request.headers.get("content-type", "application/octet-stream")

    def store() -> dict:
        with request.app.state.db.scope() as session:
            p = _authenticate(request, session)
            if p.kind != "runner":
                raise ApiError(403, "forbidden", "upload artifacts with the runner token that holds the job")
            job = _held(session, p, job_id)
            key = f"{job.workspace_id}/{job.campaign_id}/{name}"
            sha = request.app.state.storage.put(key, data, ctype)
            session.execute(delete(Artifact).where(Artifact.campaign_id == job.campaign_id, Artifact.name == name))
            session.add(Artifact(workspace_id=job.workspace_id, campaign_id=job.campaign_id, name=name,
                                 content_type=ctype, size=len(data), sha256=sha, storage_key=key))
            session.commit()
            return {"name": name, "size": len(data), "sha256": sha}

    return await run_in_threadpool(store)


class Complete(BaseModel):
    result: ResultIn


@router.post("/jobs/{job_id}/complete")
def complete(job_id: str, body: Complete, request: Request, p: Principal = Depends(runners),
             session: Session = Depends(get_session)) -> dict:
    job = _held(session, p, job_id)
    c = session.get(Campaign, job.campaign_id)
    res = body.result
    if res.evaluations != c.spec["search"]["budget"]:
        raise ApiError(422, "incomplete", f"the result covers {res.evaluations} evaluations; "
                       f"the campaign's budget is {c.spec['search']['budget']}")
    if c.n_evaluations != res.evaluations:
        raise ApiError(409, "missing_evaluations", f"{res.evaluations} evaluations were run but "
                       f"{c.n_evaluations} have been received; send the rest, then complete")
    names = {a for (a,) in session.execute(select(Artifact.name).where(Artifact.campaign_id == c.id)).all()}
    for m in res.modes:
        for ref in (m.replay, m.trace):
            if ref and ref not in names:
                raise ApiError(409, "missing_artifact", f"mode {m.label!r} refers to {ref!r}, which was not uploaded")
    session.execute(delete(FailureMode).where(FailureMode.campaign_id == c.id))
    for i, m in enumerate(res.modes):
        session.add(FailureMode(campaign_id=c.id, ordinal=i, label=m.label, predicate=m.predicate,
                                required=m.required, count=m.count, minimal=m.minimal, first_t=m.first_t,
                                locally_minimal=m.locally_minimal, evaluations=m.evaluations,
                                region=m.region, replay=m.replay, trace=m.trace))
    c.result = res.model_dump(mode="json")
    c.progress = {"phase": "done"}
    queue.finish(session, job, "done")
    service.decide_gates_for(session, c)
    audit.record(session, p, "campaign.complete", f"C-{c.number:04d}",
                 {"failures": res.failures, "modes": len(res.modes)}, request)
    session.commit()
    return service.campaign_detail(session, c)


class Fail(BaseModel):
    error: str = Field(max_length=20_000)
    retryable: bool = False
    canceled: bool = False


@router.post("/jobs/{job_id}/fail")
def fail(job_id: str, body: Fail, request: Request, p: Principal = Depends(runners),
         session: Session = Depends(get_session)) -> dict:
    job = _held(session, p, job_id)
    c = session.get(Campaign, job.campaign_id)
    if body.canceled or c.cancel_requested:
        queue.finish(session, job, "canceled", error=body.error or "canceled")
    elif body.retryable and job.attempts < job.max_attempts:
        queue.release(session, job, body.error)
    else:
        queue.finish(session, job, "failed", error=body.error)
    if c.state in ("failed", "canceled"):
        service.decide_gates_for(session, c)
    audit.record(session, p, "campaign.fail", f"C-{c.number:04d}",
                 {"retryable": body.retryable, "error": body.error[:500]}, request)
    session.commit()
    return service.campaign_detail(session, c)
