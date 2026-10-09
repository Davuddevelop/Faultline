"""Running one campaign: the engine, streamed to the control plane.

The campaign arrives as a spec (contract teeter.campaign/1). Its robot and
policy names are resolved against this runner's allowlist, the rest becomes
the same Campaign that ``faultline run`` would build from a YAML file, through
``faultline.config.parse``. From there it is the CLI's pipeline step for step,
with three additions: every sample is streamed as it is measured, each
failure mode's minimal case is replayed and uploaded, and the work stops as
soon as the campaign is canceled or this runner's lease is lost.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import faultline
from faultline import build_report, cem_search, random_search, run, sim_environment
from faultline.capture import quadruped_replay, supports_replay
from faultline.config import Campaign, parse
from faultline.model import load as load_model
from faultline.reduce import SEVERITY_AXES, _model_friction
from faultline.report import measure_coverage
from faultline.search import Sample

from .client import Client
from .config import RunnerConfig

Log = Callable[[str], None]


class Stopped(Exception):
    """The work must stop: canceled, the lease is gone, or the runner is shutting down."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Control:
    """Flags the heartbeat thread sets and the work checks, and the progress
    the heartbeat reports."""
    cancel: threading.Event = field(default_factory=threading.Event)
    lost: threading.Event = field(default_factory=threading.Event)
    shutdown: threading.Event = field(default_factory=threading.Event)
    progress: dict[str, Any] = field(default_factory=dict)

    def check(self) -> None:
        if self.lost.is_set():
            raise Stopped("lease_lost")
        if self.cancel.is_set():
            raise Stopped("canceled")
        if self.shutdown.is_set():
            raise Stopped("shutdown")


def build(spec: dict[str, Any], cfg: RunnerConfig, source: str) -> Campaign:
    """The spec as the engine's own Campaign, with names resolved here."""
    workers = int(spec["search"].get("workers", 1))
    if workers < 0:
        workers = os.cpu_count() or 1
    if cfg.max_workers > 0:
        workers = min(workers, cfg.max_workers)
    doc: dict[str, Any] = {
        "robot": str(cfg.robot_path(spec["robot"])),
        "policy": cfg.policy_ref(spec["policy"]),
        "duration_s": spec["duration_s"], "control_hz": spec["control_hz"],
        "seeds": spec["seeds"], "axes": spec["axes"], "predicates": spec["predicates"],
        "search": {"method": spec["search"]["method"], "budget": spec["search"]["budget"],
                   "workers": max(1, workers)},
        "reduce": spec["reduce"], "report": {"bins": spec.get("bins", 4)},
    }
    if spec["search"].get("target"):
        doc["search"]["target"] = spec["search"]["target"]
    if spec.get("base_body"):
        doc["base_body"] = spec["base_body"]
    if spec.get("observation"):
        doc["observation"] = spec["observation"]
    return parse(doc, base_dir=cfg.source.parent if cfg.source else ".", source=source)


def sample_row(s: Sample) -> dict[str, Any]:
    """Contract teeter.evaluation/1. An invalid run's severity is -inf, which
    JSON cannot carry; it travels as null with the reason beside it."""
    d = s.as_dict()
    sev = d["severity"]
    d["severity"] = sev if (sev is not None and math.isfinite(sev) and not s.invalid) else None
    d.pop("failed")
    return {"index": d["index"], "iteration": d["iteration"], "perturbation": d["perturbation"],
            "severity": d["severity"], "failed": s.failed, "invalid": d["invalid"], "violation": d["violation"]}


class Streamer:
    """Batches samples: a request every half second or every 50 samples,
    whichever comes first, so a fast campaign does not become a request storm
    and a slow one still shows up live."""

    def __init__(self, client: Client, job: str, control: Control, *, every_s: float = 0.5, size: int = 50):
        self.client, self.job, self.control = client, job, control
        self.every_s, self.size = every_s, size
        self.buf: list[dict[str, Any]] = []
        self.last = time.monotonic()
        self.sent = 0

    def add(self, s: Sample) -> None:
        self.control.check()
        self.buf.append(sample_row(s))
        self.control.progress["evaluations"] = s.index + 1
        if len(self.buf) >= self.size or time.monotonic() - self.last >= self.every_s:
            self.flush()

    def flush(self) -> None:
        if self.buf:
            self.client.evaluations(self.job, self.buf)
            self.sent += len(self.buf)
            self.buf = []
        self.last = time.monotonic()


def _trace_csv(traj) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["t", "tilt_deg", "height_m", "contact_force_n", "joint_vel_rads"])
    for row in zip(traj.t, traj.tilt_deg, traj.height_m, traj.contact_force_n, traj.joint_vel_rads):
        w.writerow([f"{v:.6f}" for v in row])
    return out.getvalue().encode()


def execute(client: Client, job: dict[str, Any], cfg: RunnerConfig, control: Control, log: Log) -> dict:
    spec, jid, ref = job["campaign"]["spec"], job["job"]["id"], job["campaign"]["ref"]
    camp = build(spec, cfg, source=f"{ref} from {client.api}")
    policy = camp.policy()
    robot = load_model(camp.spec.model_path, base_body=camp.spec.base_body)
    log(f"{ref}: {robot.summary()}; policy {policy.id}; {camp.method}, {camp.budget} evaluations, "
        f"{camp.workers} worker(s)")

    control.progress.update(phase="search", evaluations=0, budget=camp.budget)
    streamer = Streamer(client, jid, control)
    search = cem_search if camp.method == "cem" else random_search
    result = search(camp.spec, policy, camp.space, budget=camp.budget, seed=camp.spec.seeds.sampler,
                    target_predicate=camp.target, workers=camp.workers, policy_ref=camp.policy_ref,
                    progress=streamer.add)
    streamer.flush()
    control.check()
    log(f"{ref}: {result.summary()}")

    modes, coverage, reduced = [], measure_coverage(result, bins=camp.bins), 0
    if result.failures:
        to_reduce = min(camp.reduce_max if camp.reduce_enabled else 1, len(result.failures))
        control.progress.update(phase="reduce", reduced=0, to_reduce=to_reduce)

        def on_reduced(done: int, total: int) -> None:
            control.progress.update(reduced=done)
            control.check()

        report = build_report(result, camp.spec, policy, max_reduce=to_reduce,
                              reduce_budget=camp.reduce_budget, bins=camp.bins, on_reduced=on_reduced)
        modes, coverage, reduced = report.modes, report.coverage, report.reduced_count

    target = next(p for p in camp.spec.predicates if p.name == result.target_predicate)
    tilt_rule = next((p for p in camp.spec.predicates if p.signal == "tilt_deg"), None)
    can_replay = tilt_rule is not None and supports_replay(camp.spec.model_path)
    control.progress.update(phase="capture", captured=0, to_capture=len(modes))
    out_modes = []
    for i, m in enumerate(modes):
        control.check()
        ex = m.exemplar
        trace_name = f"modes/{i}/trace.csv"
        client.artifact(jid, trace_name, _trace_csv(run(ex.minimal_spec, policy)), "text/csv")
        replay_name = None
        if can_replay:
            replay = quadruped_replay(ex.minimal_spec, policy, threshold=tilt_rule.threshold)
            if replay is not None:
                replay_name = f"modes/{i}/replay.json"
                client.artifact(jid, replay_name, json.dumps(replay, separators=(",", ":")).encode(),
                                "application/json")
        control.progress.update(captured=i + 1)
        out_modes.append({
            "label": m.label, "predicate": m.predicate, "required": list(m.required),
            "count": len(m.members), "minimal": ex.minimal_spec.perturbation.as_dict(),
            "first_t": round(ex.minimal_violation.first_t, 4), "peak": round(ex.minimal_violation.peak, 4),
            "locally_minimal": ex.locally_minimal, "evaluations": ex.evaluations,
            "region": m.region(camp.space), "replay": replay_name, "trace": trace_name,
        })

    nominals = {a.field: a.nominal for a in SEVERITY_AXES if a.nominal is not None}
    nominals["friction_mu"] = _model_friction(camp.spec.model_path)
    doc = {
        "harness": faultline.__version__, "environment": sim_environment(),
        "robot": {"name": spec["robot"], "sha256": robot.source_sha256, "summary": robot.summary(),
                  "notes": list(robot.notes)},
        "policy": {"name": spec["policy"], "id": policy.id},
        "base_config_sha256": result.base_config_sha256, "nominals": nominals,
        "evaluations": len(result.samples), "failures": len(result.failures), "invalid": len(result.invalid),
        "first_failure_index": result.first_failure_index, "elapsed_s": round(result.elapsed_s, 3),
        "reduced": reduced, "coverage": coverage.as_dict(), "modes": out_modes,
    }
    log(f"{ref}: {len(out_modes)} failure mode(s) against {target.name}; uploading")
    control.progress.update(phase="upload")
    return client.complete(jid, doc)
