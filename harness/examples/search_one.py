"""Search a declared space, compare the two methods, reduce the worst failure.

Runs the whole chain: 01 ingest -> 03 search -> 05 reduce.

    python examples/search_one.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import mujoco

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline import (
    Predicate, RunSpec, SearchSpace, Seeds, StandPolicy, compare, reduce_failure,
)

ROOT = Path(__file__).resolve().parents[1]
MODEL = str(ROOT / "models" / "quadruped.xml")

# Chosen by measurement, not by eye: roughly 2.5% of uniform samples in this
# box fail. In a wider box ~87% fail, random finds one immediately, and the
# comparison would say nothing about sample efficiency.
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
        predicates=(Predicate("tilt_limit", "tilt_deg", ">", 35.0, grace_s=0.3),),
        seeds=Seeds(sampler=0xA13F, sim=0, policy=0),
        duration_s=5.0,
    )

    print(f"space: {SPACE.dims} axes, ~2.5% of uniform samples fail\n")
    result = compare(spec, policy, SPACE, budget=100, seeds=(0, 1, 2))
    print(result.summary())

    # take the single most severe point found by any method and minimise it
    worst = max(
        (s for runs in result.campaigns.values() for c in runs for s in c.failures),
        key=lambda s: s.severity,
        default=None,
    )
    if worst is None:
        print("\nno failures found — widen the space or raise the budget")
        return 1

    print("\nreducing the most severe failure found:")
    reduced = reduce_failure(spec.with_perturbation(**worst.perturbation), policy, budget=250)
    print(reduced.table())
    print(f"\nheadline  fails on {', '.join(reduced.required)} alone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
