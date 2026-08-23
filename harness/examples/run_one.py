"""One run, recorded, then replayed from the record.

    python examples/run_one.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import mujoco

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import Perturbation, Predicate, RunSpec, Seeds, StandPolicy, execute, replay

ROOT = Path(__file__).resolve().parents[1]
MODEL = str(ROOT / "models" / "quadruped.xml")


def main() -> int:
    policy = StandPolicy(mujoco.MjModel.from_xml_path(MODEL).key_ctrl[0])

    spec = RunSpec(
        model_path=MODEL,
        policy_id=policy.id,
        perturbation=Perturbation(
            push_impulse_ns=22.0,
            push_time_s=1.0,
            slope_deg=8.0,
            sensor_lag_ms=40.0,
        ),
        predicates=(
            Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),
            Predicate("fallen", "height_m", "<", 0.12, grace_s=0.3),
            Predicate("joint_speed", "joint_vel_rads", ">", 22.0, grace_s=0.3),
        ),
        seeds=Seeds(sampler=0xA13F, sim=0, policy=0),
        duration_s=5.0,
    )

    record, _ = execute(spec, policy)
    out = record.write(ROOT / "runs" / f"{spec.config_hash()[:12]}.json")

    print(f"verdict   {record.verdict}")
    for v in record.violations:
        print(f"  {v.predicate}: {v.signal} {v.op} {v.threshold} "
              f"first at t={v.first_t:.2f}s (peak {v.peak:.2f})")
    print(f"peaks     {record.peaks}")
    print(f"record    {out}")

    result = replay(out, policy)
    print(f"replay    {'matched' if result.matched else 'DIVERGED'}  "
          f"{result.actual_digest[:16]}")
    for note in result.notes:
        print(f"  note: {note}")
    return 0 if result.matched else 1


if __name__ == "__main__":
    raise SystemExit(main())
