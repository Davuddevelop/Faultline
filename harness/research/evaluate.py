"""Teeter's measurements of one brain: the numbers the experiment compares.

    python research/evaluate.py brain.onnx --seed 100 --n 300

Uniform samples give the failure rate (with a 95% Wilson interval) over the trained
box, and over the full box including the held-out axes. The directed search gives the
smallest failing requested push. Only the uniform arm supports a rate.
"""
from __future__ import annotations

import argparse, json, math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from faultline import SearchSpace, reduce_failure
from faultline.adapters import OnnxPolicy
from faultline.search import random_search, cem_search
from failures import base_spec
from sampling import TRAIN_BOX

HELD_OUT = {"sensor_lag_ms": (0.0, 60.0)}     # friction_mu: range to be decided with the supervisor


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brain"); ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--n", type=int, default=300); ap.add_argument("--out")
    a = ap.parse_args()
    pol = OnnxPolicy(a.brain); ref = f"onnx:{a.brain}"; spec = base_spec(pol.id)
    out = {"brain": a.brain, "seed": a.seed, "n": a.n}
    for name, box in [("trained_box", TRAIN_BOX), ("with_sensor_lag", {**TRAIN_BOX, **HELD_OUT})]:
        r = random_search(spec, pol, SearchSpace(box), budget=a.n, seed=a.seed, workers=4, policy_ref=ref)
        k = len(r.failures); out[name] = {"failed": k, "of": a.n, "pct": round(100 * k / a.n, 1), "ci95_pct": wilson(k, a.n)}
    d = cem_search(spec, pol, SearchSpace(TRAIN_BOX), budget=150, seed=a.seed, workers=4, policy_ref=ref)
    pushes = [s.perturbation["push_impulse_ns"] for s in d.failures]
    out["directed_search"] = {"failures": len(pushes), "smallest_requested_push_ns": min(pushes) if pushes else None,
                              "note": "directed hit rate is not a failure rate"}
    print(json.dumps(out, indent=1))
    if a.out: Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
