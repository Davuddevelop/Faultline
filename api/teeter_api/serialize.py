"""Rows to JSON. Times are ISO 8601 in UTC with a 'Z'."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .db import utcnow
from .models import Campaign, Checkpoint, FailureMode, Gate, Program, Runner, Token


def iso(t: datetime | None) -> str | None:
    return None if t is None else t.isoformat(timespec="seconds") + "Z"


def ref(prefix: str, number: int) -> str:
    return f"{prefix}-{number:04d}"


def runner_out(r: Runner, *, online_s: float = 90.0) -> dict[str, Any]:
    age = (utcnow() - r.last_seen_at).total_seconds()
    return {"id": r.id, "name": r.name, "online": age <= online_s, "last_seen_at": iso(r.last_seen_at),
            "seen_s_ago": round(age), "host": r.host, "versions": r.versions, "cores": r.cores,
            "robots": r.robots, "policies": r.policies, "created_at": iso(r.created_at)}


def token_out(t: Token) -> dict[str, Any]:
    return {"id": t.id, "kind": t.kind, "name": t.name, "prefix": t.prefix + "…",
            "created_at": iso(t.created_at), "last_used_at": iso(t.last_used_at),
            "revoked": t.revoked_at is not None}


def mode_out(m: FailureMode, campaign_ref: str) -> dict[str, Any]:
    return {"ordinal": m.ordinal, "label": m.label, "predicate": m.predicate, "required": m.required,
            "count": m.count, "minimal": m.minimal, "first_t": m.first_t, "locally_minimal": m.locally_minimal,
            "evaluations": m.evaluations, "region": m.region, "replay": m.replay, "trace": m.trace,
            "campaign": campaign_ref}


def campaign_out(c: Campaign, *, runner: Runner | None = None, program: Program | None = None,
                 checkpoint: Checkpoint | None = None, modes: list[FailureMode] | None = None,
                 detail: bool = False) -> dict[str, Any]:
    s = c.spec
    d: dict[str, Any] = {
        "id": c.id, "ref": ref("C", c.number), "number": c.number, "state": c.state,
        "robot": s["robot"], "policy": s["policy"], "method": s["search"]["method"],
        "budget": s["search"]["budget"], "evaluations": c.n_evaluations, "failures": c.n_failures,
        "invalid": c.n_invalid, "first_failure_index": c.first_failure_index,
        "progress": c.progress or {}, "error": c.error, "cancel_requested": c.cancel_requested,
        "created_at": iso(c.created_at), "started_at": iso(c.started_at), "finished_at": iso(c.finished_at),
        "created_by": c.created_by,
        "runner": runner.name if runner else None,
        "program": program.slug if program else None,
        "checkpoint": checkpoint.label if checkpoint else None,
        "modes_found": len((c.result or {}).get("modes", [])) if c.result else None,
    }
    if c.started_at and c.finished_at:
        d["duration_s"] = round((c.finished_at - c.started_at).total_seconds(), 1)
    if detail:
        d["spec"] = s
        d["result"] = c.result
        d["modes"] = [mode_out(m, d["ref"]) for m in (modes or [])]
    return d


def gate_out(g: Gate, base: Campaign, cand: Campaign, program: Program | None = None) -> dict[str, Any]:
    return {"id": g.id, "ref": ref("G", g.number), "number": g.number, "state": g.state, "verdict": g.verdict,
            "program": program.slug if program else None,
            "baseline": {"ref": ref("C", base.number), "policy": base.spec["policy"], "state": base.state},
            "candidate": {"ref": ref("C", cand.number), "policy": cand.spec["policy"], "state": cand.state},
            "comparison": g.comparison, "created_by": g.created_by,
            "created_at": iso(g.created_at), "decided_at": iso(g.decided_at)}


def online_cutoff(seconds: float = 90.0) -> datetime:
    return utcnow() - timedelta(seconds=seconds)
