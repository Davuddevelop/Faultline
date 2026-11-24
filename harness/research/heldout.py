"""Tests on conditions the brains did not train on, using fresh test seeds.

    python research/heldout.py brain.onnx --out res.json

friction: the training box plus friction_mu in [0.3, 0.9] (the model's own value is 0.9;
          the range is a proposal, fixed before the real runs)
beyond:   every trained range pushed 25% further out (torque loss capped at 95%), a region
          Teeter's search for brain C never sampled
Only uniform samples, so the failure counts support rates with Wilson intervals.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from faultline import SearchSpace
from faultline.adapters import OnnxPolicy
from faultline.search import random_search
from failures import base_spec
from sampling import TRAIN_BOX
from evaluate import wilson


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brain"); ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=200); ap.add_argument("--out")
    a = ap.parse_args()
    pol = OnnxPolicy(a.brain); ref = f"onnx:{a.brain}"; spec = base_spec(pol.id)
    beyond = {k: (lo, min(hi * 1.25, 95.0) if k == "torque_loss_pct" else hi * 1.25) for k, (lo, hi) in TRAIN_BOX.items()}
    out = {"brain": a.brain, "n": a.n}
    for name, box, seed in [("friction", {**TRAIN_BOX, "friction_mu": (0.3, 0.9)}, a.seed),
                            ("beyond", beyond, a.seed + 100)]:
        r = random_search(spec, pol, SearchSpace(box), budget=a.n, seed=seed, workers=4, policy_ref=ref)
        k = len(r.failures); out[name] = {"failed": k, "of": a.n, "pct": round(100 * k / a.n, 1), "ci95_pct": wilson(k, a.n)}
    print(json.dumps(out))
    if a.out: Path(a.out).write_text(json.dumps(out))


if __name__ == "__main__":
    main()
