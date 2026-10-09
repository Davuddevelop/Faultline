"""The job queue, in Postgres.

A runner claims the oldest job it is allowed to run, for a lease. While it
works it renews the lease with heartbeats; if it dies, the lease expires and
the next claim takes the job again, up to ``max_attempts``.

Correctness does not depend on the database's locking. A claim is a
compare-and-swap: ``UPDATE … WHERE id = :id AND <still claimable>``, and
whoever's update touches the row has it. On Postgres the candidate rows are
also read ``FOR UPDATE SKIP LOCKED``, so runners polling at once spread over
different jobs instead of contending for the same one. SQLite, for tests and
dev, serialises writers, and the compare-and-swap keeps it correct there too.

A retried job starts over. Its earlier evaluations are deleted rather than
kept: the retry may run on a machine with a different MuJoCo build, and a
campaign stitched from two environments would be evidence of nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.orm import Session

from .contracts import EvaluationIn
from .db import utcnow
from .models import Artifact, Campaign, Evaluation, FailureMode, Job, Runner


def enqueue(session: Session, campaign: Campaign, *, max_attempts: int = 3) -> Job:
    job = Job(workspace_id=campaign.workspace_id, campaign_id=campaign.id,
              robot=campaign.spec["robot"], policy=campaign.spec["policy"], max_attempts=max_attempts)
    session.add(job)
    session.flush()
    return job


def _claimable(now: datetime):
    return and_(
        or_(Job.state == "queued", and_(Job.state == "leased", Job.lease_expires_at < now)),
        Job.attempts < Job.max_attempts,
    )


def sweep(session: Session, workspace_id: str) -> int:
    """Fail jobs whose lease ran out on their last allowed attempt."""
    now = utcnow()
    dead = session.scalars(select(Job).where(
        Job.workspace_id == workspace_id, Job.state == "leased",
        Job.lease_expires_at < now, Job.attempts >= Job.max_attempts)).all()
    for job in dead:
        job.state, job.updated_at = "failed", now
        job.last_error = (job.last_error or "") + f"\nlease expired on attempt {job.attempts} of {job.max_attempts}"
        c = session.get(Campaign, job.campaign_id)
        if c and c.state not in ("done", "canceled"):
            c.state, c.finished_at = "failed", now
            c.error = (f"no runner finished this campaign in {job.attempts} attempts; the last "
                       "one stopped sending heartbeats. Check the runner's log and network.")
    if dead:
        session.commit()
    return len(dead)


def claim(session: Session, runner: Runner, lease_s: float, *, is_postgres: bool) -> Job | None:
    """Take the oldest job this runner may run, or return None."""
    if not runner.robots or not runner.policies:
        return None                                   # it allows nothing, so it can run nothing
    sweep(session, runner.workspace_id)
    now = utcnow()
    q = (select(Job.id)
         .where(Job.workspace_id == runner.workspace_id,
                Job.robot.in_(runner.robots), Job.policy.in_(runner.policies), _claimable(now))
         .order_by(Job.created_at).limit(8))
    if is_postgres:
        q = q.with_for_update(skip_locked=True)
    for job_id in session.scalars(q).all():
        took = session.execute(
            update(Job)
            .where(Job.id == job_id, _claimable(now))
            .values(state="leased", lease_owner=runner.id, lease_expires_at=now + timedelta(seconds=lease_s),
                    attempts=Job.attempts + 1, updated_at=now)
            .execution_options(synchronize_session=False))
        if took.rowcount != 1:
            continue                                  # someone else's update landed first
        job = session.get(Job, job_id)
        session.refresh(job)
        campaign = session.get(Campaign, job.campaign_id)
        if job.attempts > 1:
            _reset(session, campaign)
        campaign.state, campaign.runner_id = "running", runner.id
        campaign.started_at = now
        campaign.progress = {"phase": "search", "attempt": job.attempts}
        session.commit()
        return job
    session.commit()                                  # releases the row locks
    return None


def _reset(session: Session, campaign: Campaign) -> None:
    for model in (Evaluation, FailureMode, Artifact):
        session.execute(delete(model).where(model.campaign_id == campaign.id))
    campaign.n_evaluations = campaign.n_failures = campaign.n_invalid = 0
    campaign.first_failure_index = None
    campaign.result = None


def holds(job: Job | None, runner: Runner) -> bool:
    """Does this runner still hold this job? A runner whose lease lapsed and
    was taken over must stop, and its late requests are refused."""
    return job is not None and job.state == "leased" and job.lease_owner == runner.id


def renew(session: Session, job: Job, runner: Runner, lease_s: float,
          progress: dict[str, Any] | None) -> tuple[bool, bool]:
    """Extend the lease. Returns (still held, cancel requested)."""
    now = utcnow()
    took = session.execute(
        update(Job).where(Job.id == job.id, Job.state == "leased", Job.lease_owner == runner.id)
        .values(lease_expires_at=now + timedelta(seconds=lease_s), updated_at=now)
        .execution_options(synchronize_session=False))
    if took.rowcount != 1:
        session.rollback()
        return False, False
    campaign = session.get(Campaign, job.campaign_id)
    if progress:
        campaign.progress = {**(campaign.progress or {}), **progress}
    runner.last_seen_at = now
    session.commit()
    return True, bool(campaign.cancel_requested)


def ingest(session: Session, campaign: Campaign, rows: Iterable[EvaluationIn], *, is_postgres: bool) -> int:
    """Store evaluations, ignoring any already stored. Returns how many were new."""
    values = [dict(campaign_id=campaign.id, index=r.index, iteration=r.iteration,
                   perturbation=r.perturbation, severity=r.severity, failed=r.failed,
                   invalid=r.invalid, violation=r.violation) for r in rows]
    if not values:
        return 0
    if is_postgres:
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = (insert(Evaluation).values(values)
            .on_conflict_do_nothing(index_elements=["campaign_id", "index"])
            .returning(Evaluation.index, Evaluation.failed, Evaluation.invalid))
    new = session.execute(stmt).all()
    if new:
        fails = [i for i, failed, _ in new if failed]
        first = min(fails) if fails else None
        values_ = dict(
            n_evaluations=Campaign.n_evaluations + len(new),
            n_failures=Campaign.n_failures + len(fails),
            n_invalid=Campaign.n_invalid + sum(1 for _, _, inv in new if inv),
        )
        if first is not None:
            values_["first_failure_index"] = case(
                (Campaign.first_failure_index.is_(None), first),
                (Campaign.first_failure_index > first, first),
                else_=Campaign.first_failure_index)
        session.execute(update(Campaign).where(Campaign.id == campaign.id).values(**values_)
                        .execution_options(synchronize_session=False))
    session.commit()
    return len(new)


def finish(session: Session, job: Job, state: str, *, error: str | None = None) -> None:
    now = utcnow()
    job.state, job.updated_at, job.lease_expires_at = state, now, None
    if error:
        job.last_error = error
    campaign = session.get(Campaign, job.campaign_id)
    campaign.state = {"done": "done", "failed": "failed", "canceled": "canceled"}[state]
    campaign.finished_at = now
    if error:
        campaign.error = error


def release(session: Session, job: Job, error: str) -> None:
    """Give a job back after a retryable failure: the next claim takes it."""
    now = utcnow()
    job.state, job.lease_owner, job.lease_expires_at, job.updated_at = "queued", None, None, now
    job.last_error = error
    campaign = session.get(Campaign, job.campaign_id)
    campaign.state, campaign.progress = "queued", {"phase": "waiting", "last_error": error}


def counts(session: Session, campaign_id: str) -> dict[str, int]:
    """An exact recount, for tests and repair: the counters are the fast path."""
    row = session.execute(select(func.count(), func.coalesce(func.sum(case((Evaluation.failed, 1), else_=0)), 0))
                          .where(Evaluation.campaign_id == campaign_id)).one()
    return {"evaluations": int(row[0]), "failures": int(row[1])}
