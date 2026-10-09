"""The tables. Every row that belongs to a customer carries ``workspace_id``,
and every query in routes/ filters on it.

The nouns are the product plan's (§3): workspace, program, checkpoint,
campaign, evaluation, failure mode, gate, runner. A campaign's spec and result
are stored as JSON documents: they are versioned contracts (contracts.py), and
the database should not have to change shape every time a contract gains a
field.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


def new_id() -> str:
    return uuid.uuid4().hex


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))          # owner | admin | engineer | viewer


class Token(Base):
    """A bearer credential. Only its SHA-256 is stored; the secret is shown
    once, when it is created."""
    __tablename__ = "tokens"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(8))            # user | runner | ci
    name: Mapped[str] = mapped_column(String(200))
    prefix: Mapped[str] = mapped_column(String(24))         # shown in lists: tt_run_3f9a…
    secret_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SignInLink(Base):
    """A one-time link that signs a browser in: following it mints a new user
    token and hands it over once. Only the code's hash is stored, never a
    token. v0's sign-in; an identity provider replaces it in M1."""
    __tablename__ = "sign_in_links"
    code_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Runner(Base):
    __tablename__ = "runners"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    token_id: Mapped[str] = mapped_column(ForeignKey("tokens.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    host: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    versions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cores: Mapped[int] = mapped_column(Integer, default=1)
    robots: Mapped[list[str]] = mapped_column(JSON, default=list)       # names it allows
    policies: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Program(Base):
    """One robot product line: the unit of the licence. Its standard spec is
    what every checkpoint is gated on."""
    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    standard_spec: Mapped[dict[str, Any]] = mapped_column(JSON)          # a campaign spec without a policy
    baseline_checkpoint_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (UniqueConstraint("program_id", "label"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    program_id: Mapped[str] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(64))
    policy: Mapped[str] = mapped_column(String(100))       # a name in the runner's allowlist
    policy_id: Mapped[str | None] = mapped_column(String(200), nullable=True)   # content id, from the runner
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        UniqueConstraint("workspace_id", "number"),
        Index("ix_campaigns_ws_created", "workspace_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)           # C-0001, per workspace
    program_id: Mapped[str | None] = mapped_column(ForeignKey("programs.id", ondelete="SET NULL"), nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    spec_sha256: Mapped[str] = mapped_column(String(64), index=True)    # of the spec without the policy
    state: Mapped[str] = mapped_column(String(16), default="queued")    # queued|running|reducing|done|failed|canceled
    created_by: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    runner_id: Mapped[str | None] = mapped_column(ForeignKey("runners.id", ondelete="SET NULL"), nullable=True)
    # counters, incremented atomically as evaluations arrive, so progress never
    # needs a count over a table that can hold a hundred thousand rows
    n_evaluations: Mapped[int] = mapped_column(Integer, default=0)
    n_failures: Mapped[int] = mapped_column(Integer, default=0)
    n_invalid: Mapped[int] = mapped_column(Integer, default=0)
    first_failure_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)     # phase, from heartbeats
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class Job(Base):
    """The queue. A runner takes a job by lease; see queue.py."""
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_claim", "workspace_id", "state", "created_at"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), unique=True)
    # what a runner must allow to take it; denormalised from the spec so a
    # claim is one indexed query
    robot: Mapped[str] = mapped_column(String(100))
    policy: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(16), default="queued")    # queued|leased|done|failed|canceled
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    lease_owner: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Evaluation(Base):
    """One simulation. Keyed by (campaign, index) so ingest is idempotent: a
    deterministic campaign re-run reproduces the same rows."""
    __tablename__ = "evaluations"
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True)
    index: Mapped[int] = mapped_column(Integer, primary_key=True)
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    perturbation: Mapped[dict[str, float]] = mapped_column(JSON)
    severity: Mapped[float | None] = mapped_column(Float, nullable=True)   # None when the run was invalid
    failed: Mapped[bool] = mapped_column(Boolean)
    invalid: Mapped[str | None] = mapped_column(Text, nullable=True)
    violation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class FailureMode(Base):
    __tablename__ = "failure_modes"
    __table_args__ = (UniqueConstraint("campaign_id", "ordinal"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(300))
    predicate: Mapped[str] = mapped_column(String(100))
    required: Mapped[list[str]] = mapped_column(JSON)
    count: Mapped[int] = mapped_column(Integer)
    minimal: Mapped[dict[str, Any]] = mapped_column(JSON)
    first_t: Mapped[float] = mapped_column(Float)
    locally_minimal: Mapped[bool] = mapped_column(Boolean)
    evaluations: Mapped[int] = mapped_column(Integer)
    region: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    replay: Mapped[str | None] = mapped_column(String(200), nullable=True)   # artifact name
    trace: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("campaign_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Gate(Base):
    __tablename__ = "gates"
    __table_args__ = (UniqueConstraint("workspace_id", "number"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    program_id: Mapped[str | None] = mapped_column(ForeignKey("programs.id", ondelete="SET NULL"), nullable=True)
    baseline_campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    candidate_campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"))
    state: Mapped[str] = mapped_column(String(16), default="waiting")     # waiting | decided
    verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)  # passed | blocked | refused
    comparison: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_ws_at", "workspace_id", "at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(200), default="")
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
