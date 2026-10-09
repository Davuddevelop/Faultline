#!/usr/bin/env python3
"""Regenerate assets/data/campaign.json, the published campaign, from the harness.

The record the site, the app and /report/ are drawn from was produced once, by
hand, and nothing in the repository could produce it again. This is that run
written down, so the record can be re-made whenever the engine changes:

  the stand-in quadruped and its built-in stance policy (not a trained one),
  six axes, two rules, 150 evaluations per seed, five sampler seeds of uniform
  sampling against five of directed search, and the engineering report of
  directed seed 0: its ten most severe failures reduced and grouped.

    cd harness && python3 ../tools/publish_campaign.py            # write it
    cd harness && python3 ../tools/publish_campaign.py --check    # compare only

``--check`` exits 1 when the record on disk is not what the engine produces
today, and names what differs. The date and the environment it was made in
(Python, NumPy, MuJoCo versions) are provenance, not results: a difference
there is reported as a note, and only the results decide.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "harness"
sys.path.insert(0, str(HARNESS))

from faultline import (  # noqa: E402
    Predicate, RunSpec, Seeds, build_report, cem_search, random_search, sim_environment,
)
from faultline.config import load_policy  # noqa: E402
from faultline.space import SearchSpace  # noqa: E402

OUT = ROOT / "assets" / "data" / "campaign.json"
MODEL = str(HARNESS / "models" / "quadruped.xml")
BUDGET = 150
SEEDS = (0, 1, 2, 3, 4)
SPACE = SearchSpace({
    "push_impulse_ns": (0.0, 9.0),
    "slope_deg": (0.0, 10.0),
    "sensor_lag_ms": (0.0, 60.0),
    "torque_loss_pct": (0.0, 15.0),
    "payload_kg": (0.0, 2.0),
    "payload_offset_m": (0.0, 0.06),
})
PREDICATES = (
    Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),
    Predicate("fallen", "height_m", "<", 0.12, grace_s=0.3),
)
REDUCE_MAX, REDUCE_BUDGET, BINS = 10, 200, 4
SCATTER = ("push_impulse_ns", "torque_loss_pct")


def build() -> dict:
    policy = load_policy("stand", MODEL)
    spec = RunSpec(model_path=MODEL, policy_id=policy.id, predicates=PREDICATES,
                   seeds=Seeds(0, 0, 0), duration_s=5.0)
    workers = max(1, os.cpu_count() or 1)
    runs = {}
    for name, search in (("random", random_search), ("cem", cem_search)):
        runs[name] = [search(spec, policy, SPACE, budget=BUDGET, seed=s,
                             workers=workers, policy_ref="stand") for s in SEEDS]
        print(f"  {name:<6} failures per seed {[len(c.failures) for c in runs[name]]}", file=sys.stderr)

    directed = runs["cem"][0]
    report = build_report(directed, spec, policy, max_reduce=REDUCE_MAX,
                          reduce_budget=REDUCE_BUDGET, bins=BINS)
    modes = []
    for m in report.modes:
        ex = m.exemplar
        modes.append({
            "label": m.label,
            "count": len(m.members),
            "required": list(m.required),
            "minimal": {a: round(float(getattr(ex.minimal_spec.perturbation, a)), 3) for a in m.required},
            "first_t": round(float(ex.minimal_violation.first_t), 2),
            "evaluations": ex.evaluations,
        })
    x, y = SCATTER
    return {
        "generated": date.today().isoformat(),
        "budget": BUDGET,
        "seeds": list(SEEDS),
        "space": {a: [lo, hi] if not float(hi).is_integer() else [int(lo), int(hi)]
                  for a, (lo, hi) in SPACE.bounds.items()},
        "efficiency": {k: [np.cumsum([s.failed for s in c.samples]).astype(int).tolist() for c in v]
                       for k, v in runs.items()},
        "totals": {k: [len(c.failures) for c in v] for k, v in runs.items()},
        "first_failure": {k: [c.first_failure_index for c in v] for k, v in runs.items()},
        "scatter": {
            "x_axis": x, "y_axis": y,
            "x_bounds": [int(b) if float(b).is_integer() else b for b in SPACE.bounds[x]],
            "y_bounds": [int(b) if float(b).is_integer() else b for b in SPACE.bounds[y]],
            "points": [{"x": round(s.perturbation[x], 3), "y": round(s.perturbation[y], 3),
                        "f": int(s.failed)} for s in directed.samples],
        },
        "report": {
            "failures_total": report.failures_total,
            "reduced": report.reduced_count,
            "coverage": report.coverage.as_dict(),
            "modes": modes,
            "predicates": [{"name": p.name, "signal": p.signal, "op": p.op, "threshold": p.threshold}
                           for p in PREDICATES],
            "environment": sim_environment(),
        },
    }


# Where and when the record was made, not what it found. A record made under
# another Python or NumPy patch release is still this engine's record if every
# result matches, so these are reported beside the comparison, not part of it.
PROVENANCE = (("generated",), ("report", "environment"))


def _short(v) -> str:
    r = json.dumps(v)
    return r if len(r) <= 60 else r[:57] + "..."


def compare(old: dict, new: dict, limit: int = 12) -> tuple[list[str], list[str]]:
    """The results that differ between two records, by path, and notes on
    where their provenance differs."""
    def results(d: dict) -> dict:
        d = json.loads(json.dumps(d))
        for path in PROVENANCE:
            parent = d
            for k in path[:-1]:
                parent = parent.get(k, {})
            parent.pop(path[-1], None)
        return d

    diffs: list[str] = []

    def walk(a, b, at: str) -> None:
        if len(diffs) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for k in sorted(set(a) | set(b)):
                if k not in b:
                    diffs.append(f"{at}/{k}: in the record, not produced")
                elif k not in a:
                    diffs.append(f"{at}/{k}: produced, not in the record")
                else:
                    walk(a[k], b[k], f"{at}/{k}")
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{at}[{i}]")
        elif a != b:
            diffs.append(f"{at}: record {_short(a)}, engine {_short(b)}")

    walk(results(old), results(new), "")
    notes = []
    env_old, env_new = (d.get("report", {}).get("environment") or {} for d in (old, new))
    changed = [f"{k} {env_old.get(k)} in the record, {env_new.get(k)} here"
               for k in sorted(set(env_old) | set(env_new)) if env_old.get(k) != env_new.get(k)]
    if changed:
        notes.append("made in another environment: " + "; ".join(changed))
    return diffs, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="compare with the record on disk; write nothing")
    args = ap.parse_args()
    doc = build()
    if args.check:
        diffs, notes = compare(json.loads(OUT.read_text()), doc)
        for n in notes:
            print(f"  note: {n}")
        if diffs:
            print("record differs from what the engine produces today:")
            for d in diffs:
                print(f"  {d}")
            return 1
        print("record matches the engine")
        return 0
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {doc['report']['failures_total']} violations in "
          f"{BUDGET} directed evaluations, {len(doc['report']['modes'])} failure mode(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
