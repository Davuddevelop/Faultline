"""A whole campaign, end to end, into the three deliverables.

    python examples/report_one.py

Runs 01 ingest -> 02 perturb -> 03 search -> 04 detect -> 05 reduce, then
writes the engineering report, the safety-case appendix and the run archive.
"""

from __future__ import annotations

import sys
from pathlib import Path

import mujoco

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import (
    Predicate, RunSpec, SearchSpace, Seeds, StandPolicy, build_report,
    cem_search, write_deliverables,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL = str(ROOT / "models" / "quadruped.xml")

SPACE = SearchSpace({
    "push_impulse_ns": (0, 9),
    "slope_deg": (0, 10),
    "sensor_lag_ms": (0, 60),
    "torque_loss_pct": (0, 15),
    "payload_kg": (0, 2.0),
    "payload_offset_m": (0, 0.06),
})


def main() -> int:
    policy = StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])

    spec = RunSpec(
        model_path=MODEL,
        policy_id=policy.id,
        predicates=(
            Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),
            Predicate("fallen", "height_m", "<", 0.12, grace_s=0.3),
        ),
        seeds=Seeds(sampler=0xA13F, sim=0, policy=0),
        duration_s=5.0,
    )

    campaign = cem_search(spec, policy, SPACE, budget=120, seed=0)
    print(campaign.summary())

    report = build_report(campaign, spec, policy, max_reduce=10)
    print(f"\n{len(report.modes)} failure modes from the "
          f"{report.reduced_count} most severe of {report.failures_total} failures:\n")
    for i, mode in enumerate(report.modes, 1):
        print(f"  {i}. {len(mode.members):>2} x  {mode.label}")

    cov = report.coverage
    print(f"\ncoverage  {cov.cells_visited}/{cov.cells_total} cells "
          f"({cov.fraction:.2%}) at {cov.bins} bins per axis")

    out = write_deliverables(report, policy, ROOT / "runs" / "deliverables")
    print(f"\nwritten to {out}")
    for f in sorted(out.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
