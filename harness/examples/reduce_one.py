"""A failure caused by five things at once, reduced to the ones that matter.

    python examples/reduce_one.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import mujoco

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import (
    Perturbation, Predicate, RunSpec, Seeds, StandPolicy, execute, reduce_failure,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL = str(ROOT / "models" / "quadruped.xml")


def main() -> int:
    policy = StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])

    spec = RunSpec(
        model_path=MODEL,
        policy_id=policy.id,
        perturbation=Perturbation(
            push_impulse_ns=26.0,
            slope_deg=14.0,
            sensor_lag_ms=60.0,
            payload_kg=1.2,
            torque_loss_pct=15.0,
        ),
        predicates=(
            Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),
            Predicate("fallen", "height_m", "<", 0.12, grace_s=0.3),
        ),
        seeds=Seeds(sampler=0xA13F, sim=0, policy=0),
        duration_s=5.0,
    )

    record, _ = execute(spec, policy)
    print(f"original run: {record.verdict}", end="")
    if record.violations:
        v = record.violations[0]
        print(f" — {v.predicate} at t={v.first_t:.2f}s")
    print("  five axes perturbed; which of them mattered?\n")

    result = reduce_failure(spec, policy, budget=250)
    print(result.table())

    out = result.write(ROOT / "runs" / f"reduction-{spec.config_hash()[:12]}.json")
    print(f"\nrecord    {out}")
    print(f"headline  fails on {', '.join(result.required)} alone; "
          f"{', '.join(result.eliminated)} were irrelevant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
