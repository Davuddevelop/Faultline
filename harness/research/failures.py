"""Teeter finds failures on a brain; write them out as training starts for brain C.

    python research/failures.py brainA.onnx failures-A-seed0.json --seed 0
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from faultline import Predicate, RunSpec, SearchSpace, Seeds
from faultline.adapters import OnnxPolicy
from faultline.search import cem_search
from env import MODEL
from sampling import TRAIN_BOX

OBS = ({"term": "projected_gravity"}, {"term": "base_ang_vel"},
       {"term": "joint_pos", "relative": True}, {"term": "joint_vel", "scale": 0.05})
PREDS = (Predicate("tilt_limit", "tilt_deg", ">", 35.0, 0.3), Predicate("fallen", "height_m", "<", 0.12, 0.3))


def base_spec(policy_id):
    return RunSpec(MODEL, policy_id, predicates=PREDS, seeds=Seeds(0, 0, 0), duration_s=6.0, observation=OBS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brain"); ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--budget", type=int, default=300)
    a = ap.parse_args()
    pol = OnnxPolicy(a.brain)
    res = cem_search(base_spec(pol.id), pol, SearchSpace(TRAIN_BOX), budget=a.budget, seed=a.seed,
                     workers=4, policy_ref=f"onnx:{a.brain}")
    fails = [s.perturbation for s in res.failures]
    Path(a.out).write_text(json.dumps({"brain": a.brain, "seed": a.seed, "budget": a.budget,
                                       "found": len(fails), "failures": fails}, indent=1))
    print(f"{len(fails)} failures of {a.budget} written to {a.out}")


if __name__ == "__main__":
    main()
