"""Programs, their checkpoints, and gates.

A program fixes the experiment (its standard spec, with no policy). Each
checkpoint names a policy. Running a checkpoint runs that experiment on it,
recorded against it. Gating a checkpoint runs the experiment on it and
compares with the baseline checkpoint's most recent run of the same
experiment, queuing the baseline too if it has never run it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import audit, service
from ..contracts import CampaignSpec
from ..errors import ApiError, not_found
from ..models import Campaign, Checkpoint, Gate, Program
from ..security import Principal, editors, editors_or_ci, get_session, people_or_ci
from ..serialize import iso

router = APIRouter(prefix="/v1")


class NewProgram(BaseModel):
    slug: str = Field(pattern=r"^[a-z][a-z0-9\-]{1,63}$")
    name: str = Field(min_length=1, max_length=200)
    standard_spec: dict[str, Any]


class NewCheckpoint(BaseModel):
    label: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")
    policy: str
    note: str = ""
    baseline: bool = False


class GateCheckpoint(BaseModel):
    checkpoint: str


class NewGate(BaseModel):
    baseline: str
    candidate: str


def _validate_standard(spec: dict[str, Any]) -> dict[str, Any]:
    """A campaign spec with no policy: validated as a full one with a stand-in."""
    if "policy" in spec:
        raise ApiError(422, "invalid", "standard_spec: leave out 'policy'; each checkpoint supplies its own")
    return CampaignSpec(**{**spec, "policy": "placeholder"}).model_dump(mode="json") | {"policy": None}


def _checkpoint(session: Session, prog: Program, label: str) -> Checkpoint:
    ck = session.scalar(select(Checkpoint).where(Checkpoint.program_id == prog.id, Checkpoint.label == label))
    if ck is None:
        raise not_found(f"checkpoint {label!r} in {prog.slug}")
    return ck


def _spec_for(prog: Program, ck: Checkpoint) -> CampaignSpec:
    """The program's experiment with this checkpoint's policy, and nothing else changed."""
    return CampaignSpec(**{**prog.standard_spec, "policy": ck.policy})


def _program_out(session: Session, prog: Program) -> dict[str, Any]:
    cks = session.scalars(select(Checkpoint).where(Checkpoint.program_id == prog.id)
                          .order_by(Checkpoint.created_at)).all()
    latest = {}
    for ck in cks:
        c = session.scalar(select(Campaign).where(Campaign.checkpoint_id == ck.id)
                           .order_by(Campaign.number.desc()).limit(1))
        latest[ck.id] = c
    return {
        "slug": prog.slug, "name": prog.name, "standard_spec": prog.standard_spec,
        "created_at": iso(prog.created_at),
        "checkpoints": [{
            "label": ck.label, "policy": ck.policy, "policy_id": ck.policy_id, "note": ck.note,
            "baseline": ck.id == prog.baseline_checkpoint_id, "created_at": iso(ck.created_at),
            "latest_campaign": (service.campaign_detail(session, latest[ck.id], detail=False)
                                if latest[ck.id] else None),
        } for ck in cks],
    }


@router.get("/programs")
def list_programs(p: Principal = Depends(people_or_ci), session: Session = Depends(get_session)) -> dict:
    progs = session.scalars(select(Program).where(Program.workspace_id == p.workspace.id)
                            .order_by(Program.created_at)).all()
    return {"programs": [_program_out(session, x) for x in progs]}


@router.post("/programs", status_code=201)
def create_program(body: NewProgram, request: Request, p: Principal = Depends(editors),
                   session: Session = Depends(get_session)) -> dict:
    if session.scalar(select(Program).where(Program.workspace_id == p.workspace.id, Program.slug == body.slug)):
        raise ApiError(409, "exists", f"a program called {body.slug!r} already exists")
    prog = Program(workspace_id=p.workspace.id, slug=body.slug, name=body.name,
                   standard_spec=_validate_standard(body.standard_spec))
    session.add(prog)
    audit.record(session, p, "program.create", body.slug, {}, request)
    session.commit()
    return _program_out(session, prog)


@router.get("/programs/{slug}")
def get_program(slug: str, p: Principal = Depends(people_or_ci), session: Session = Depends(get_session)) -> dict:
    return _program_out(session, service.find_program(session, p.workspace.id, slug))


@router.post("/programs/{slug}/checkpoints", status_code=201)
def add_checkpoint(slug: str, body: NewCheckpoint, request: Request, p: Principal = Depends(editors_or_ci),
                   session: Session = Depends(get_session)) -> dict:
    prog = service.find_program(session, p.workspace.id, slug)
    if session.scalar(select(Checkpoint).where(Checkpoint.program_id == prog.id, Checkpoint.label == body.label)):
        raise ApiError(409, "exists", f"{slug} already has a checkpoint labelled {body.label!r}")
    CampaignSpec(**{**prog.standard_spec, "policy": body.policy})      # the name must be a valid one
    ck = Checkpoint(workspace_id=p.workspace.id, program_id=prog.id, label=body.label,
                    policy=body.policy, note=body.note)
    session.add(ck)
    session.flush()
    if body.baseline or prog.baseline_checkpoint_id is None:
        prog.baseline_checkpoint_id = ck.id
    audit.record(session, p, "checkpoint.create", f"{slug}/{body.label}", {"policy": body.policy}, request)
    session.commit()
    return _program_out(session, prog)


@router.put("/programs/{slug}/baseline")
def set_baseline(slug: str, body: GateCheckpoint, request: Request, p: Principal = Depends(editors),
                 session: Session = Depends(get_session)) -> dict:
    prog = service.find_program(session, p.workspace.id, slug)
    ck = _checkpoint(session, prog, body.checkpoint)
    prog.baseline_checkpoint_id = ck.id
    audit.record(session, p, "program.baseline", f"{slug}/{ck.label}", {}, request)
    session.commit()
    return _program_out(session, prog)


@router.post("/programs/{slug}/checkpoints/{label}/run", status_code=201)
def run_checkpoint(slug: str, label: str, request: Request, p: Principal = Depends(editors_or_ci),
                   session: Session = Depends(get_session)) -> dict:
    """Run the program's experiment on one checkpoint. The campaign is recorded
    against the checkpoint, so a later gate reuses it rather than repeating it."""
    prog = service.find_program(session, p.workspace.id, slug)
    ck = _checkpoint(session, prog, label)
    c = service.create_campaign(session, p, _spec_for(prog, ck), max_attempts=request.app.state.settings.max_attempts,
                                program=prog, checkpoint=ck, request=request)
    return service.campaign_detail(session, c)


@router.post("/programs/{slug}/gate", status_code=201)
def gate_checkpoint(slug: str, body: GateCheckpoint, request: Request, p: Principal = Depends(editors_or_ci),
                    session: Session = Depends(get_session)) -> dict:
    """What CI calls: run the program's experiment on this checkpoint and
    compare it with the baseline's."""
    settings = request.app.state.settings
    prog = service.find_program(session, p.workspace.id, slug)
    cand_ck = _checkpoint(session, prog, body.checkpoint)
    base_ck = session.get(Checkpoint, prog.baseline_checkpoint_id) if prog.baseline_checkpoint_id else None
    if base_ck is None:
        raise ApiError(409, "no_baseline", f"{slug} has no baseline checkpoint; set one first")
    if base_ck.id == cand_ck.id:
        raise ApiError(409, "is_baseline", f"{body.checkpoint} is the baseline; gate a different checkpoint")

    base_spec = _spec_for(prog, base_ck)
    base = session.scalar(select(Campaign).where(
        Campaign.checkpoint_id == base_ck.id, Campaign.spec_sha256 == base_spec.experiment_sha256(),
        Campaign.state.in_(("queued", "running", "done"))).order_by(Campaign.number.desc()).limit(1))
    if base is None:
        base = service.create_campaign(session, p, base_spec, max_attempts=settings.max_attempts,
                                       program=prog, checkpoint=base_ck, request=request)
    cand = service.create_campaign(session, p, _spec_for(prog, cand_ck), max_attempts=settings.max_attempts,
                                   program=prog, checkpoint=cand_ck, request=request)
    g = service.create_gate(session, p, base, cand, program=prog, request=request)
    return service.gate_detail(session, g)


@router.post("/gates", status_code=201)
def create_gate(body: NewGate, request: Request, p: Principal = Depends(editors_or_ci),
                session: Session = Depends(get_session)) -> dict:
    base = service.find_campaign(session, p.workspace.id, body.baseline)
    cand = service.find_campaign(session, p.workspace.id, body.candidate)
    return service.gate_detail(session, service.create_gate(session, p, base, cand, request=request))


@router.get("/gates")
def list_gates(limit: int = 50, p: Principal = Depends(people_or_ci), session: Session = Depends(get_session)) -> dict:
    rows = session.scalars(select(Gate).where(Gate.workspace_id == p.workspace.id)
                           .order_by(Gate.number.desc()).limit(max(1, min(limit, 200)))).all()
    return {"gates": [service.gate_detail(session, g) for g in rows]}


@router.get("/gates/{ref}")
def get_gate(ref: str, p: Principal = Depends(people_or_ci), session: Session = Depends(get_session)) -> dict:
    return service.gate_detail(session, service.find_gate(session, p.workspace.id, ref))
