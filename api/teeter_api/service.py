"""What more than one route needs: numbering, lookups, creating a campaign,
deciding a gate. Routes stay thin; this is where the rules are."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import audit, gate as gates, queue
from .contracts import CampaignSpec
from .db import utcnow
from .errors import ApiError, not_found
from .models import Campaign, Checkpoint, FailureMode, Gate, Program, Runner
from .security import Principal
from .serialize import campaign_out, gate_out

_REF = re.compile(r"^(?:([CG])-)?0*(\d+)$", re.I)


def _number(session: Session, model, workspace_id: str) -> int:
    top = session.scalar(select(func.max(model.number)).where(model.workspace_id == workspace_id))
    return (top or 0) + 1


def find_campaign(session: Session, workspace_id: str, ref: str) -> Campaign:
    m = _REF.match(ref)
    q = select(Campaign).where(Campaign.workspace_id == workspace_id)
    q = q.where(Campaign.number == int(m.group(2))) if m else q.where(Campaign.id == ref)
    c = session.scalar(q)
    if c is None:
        raise not_found(f"campaign {ref!r}")
    return c


def find_gate(session: Session, workspace_id: str, ref: str) -> Gate:
    m = _REF.match(ref)
    q = select(Gate).where(Gate.workspace_id == workspace_id)
    q = q.where(Gate.number == int(m.group(2))) if m else q.where(Gate.id == ref)
    g = session.scalar(q)
    if g is None:
        raise not_found(f"gate {ref!r}")
    return g


def find_program(session: Session, workspace_id: str, slug: str) -> Program:
    p = session.scalar(select(Program).where(Program.workspace_id == workspace_id, Program.slug == slug))
    if p is None:
        raise not_found(f"program {slug!r}")
    return p


def create_campaign(session: Session, who: Principal, spec: CampaignSpec, *, max_attempts: int,
                    program: Program | None = None, checkpoint: Checkpoint | None = None,
                    request=None) -> Campaign:
    """Store and enqueue. The number is the next free one in the workspace;
    two campaigns created at the same instant retry rather than collide."""
    for _ in range(5):
        c = Campaign(workspace_id=who.workspace.id, number=_number(session, Campaign, who.workspace.id),
                     spec=spec.model_dump(mode="json"), spec_sha256=spec.experiment_sha256(),
                     program_id=program.id if program else None,
                     checkpoint_id=checkpoint.id if checkpoint else None,
                     created_by=who.actor, progress={"phase": "waiting"})
        session.add(c)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            continue
        queue.enqueue(session, c, max_attempts=max_attempts)
        audit.record(session, who, "campaign.create", f"C-{c.number:04d}",
                     {"robot": spec.robot, "policy": spec.policy, "budget": spec.search.budget}, request)
        session.commit()
        return c
    raise ApiError(503, "busy", "could not allocate a campaign number; try again")


def campaign_detail(session: Session, c: Campaign, *, detail: bool = True) -> dict[str, Any]:
    runner = session.get(Runner, c.runner_id) if c.runner_id else None
    program = session.get(Program, c.program_id) if c.program_id else None
    ckpt = session.get(Checkpoint, c.checkpoint_id) if c.checkpoint_id else None
    modes = session.scalars(select(FailureMode).where(FailureMode.campaign_id == c.id)
                            .order_by(FailureMode.ordinal)).all() if detail else None
    return campaign_out(c, runner=runner, program=program, checkpoint=ckpt, modes=modes, detail=detail)


def _finished(c: Campaign) -> bool:
    return c.state in ("done", "failed", "canceled")


def decide(session: Session, g: Gate) -> None:
    base, cand = session.get(Campaign, g.baseline_campaign_id), session.get(Campaign, g.candidate_campaign_id)
    if not (_finished(base) and _finished(cand)):
        return
    if base.state != "done" or cand.state != "done":
        bad = [f"C-{x.number:04d} {x.state}" for x in (base, cand) if x.state != "done"]
        g.comparison = {"verdict": "refused", "differs": [], "modes": [],
                        "reason": "a campaign did not finish, so there is nothing to compare: " + ", ".join(bad)}
    else:
        g.comparison = gates.compare({"spec": base.spec, "result": base.result},
                                     {"spec": cand.spec, "result": cand.result})
    g.verdict, g.state, g.decided_at = g.comparison["verdict"], "decided", utcnow()


def decide_gates_for(session: Session, campaign: Campaign) -> None:
    waiting = session.scalars(select(Gate).where(
        Gate.state == "waiting",
        or_(Gate.baseline_campaign_id == campaign.id, Gate.candidate_campaign_id == campaign.id))).all()
    for g in waiting:
        decide(session, g)


def create_gate(session: Session, who: Principal, base: Campaign, cand: Campaign, *,
                program: Program | None = None, request=None) -> Gate:
    if base.id == cand.id:
        raise ApiError(422, "same_campaign", "a gate compares two campaigns; both refer to the same one")
    for _ in range(5):
        g = Gate(workspace_id=who.workspace.id, number=_number(session, Gate, who.workspace.id),
                 program_id=program.id if program else None, baseline_campaign_id=base.id,
                 candidate_campaign_id=cand.id, created_by=who.actor)
        session.add(g)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            continue
        decide(session, g)
        audit.record(session, who, "gate.create", f"G-{g.number:04d}",
                     {"baseline": f"C-{base.number:04d}", "candidate": f"C-{cand.number:04d}"}, request)
        session.commit()
        return g
    raise ApiError(503, "busy", "could not allocate a gate number; try again")


def gate_detail(session: Session, g: Gate) -> dict[str, Any]:
    base, cand = session.get(Campaign, g.baseline_campaign_id), session.get(Campaign, g.candidate_campaign_id)
    program = session.get(Program, g.program_id) if g.program_id else None
    return gate_out(g, base, cand, program)
