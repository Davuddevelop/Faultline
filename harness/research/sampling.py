"""Which conditions a brain trains under. The only thing that differs between B and C.

TRAIN_BOX holds the declared ranges the training may draw from. sensor_lag_ms
and friction_mu are left out on purpose: they are the held-out conditions used
to test whether toughness carries over to problems nobody practised.

  none      brain A: no perturbation during training
  uniform   brain B: every axis drawn evenly across the box
  failures  brain C: half the episodes drawn around failures Teeter found on A,
            half evenly across the box, so C is B plus targeting, not a different diet
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

_DEFAULT_BOX = {
    "push_impulse_ns": (0.0, float(os.environ.get("TEETER_PUSH_MAX", "9.0"))),
    "slope_deg": (0.0, 10.0),
    "torque_loss_pct": (0.0, 15.0),
    "payload_kg": (0.0, 2.0),
    "payload_offset_m": (0.0, 0.06),
}


# TEETER_BOX='{"torque_loss_pct": [0, 40]}' overrides single ranges, for choosing the test box.
TRAIN_BOX = {**_DEFAULT_BOX, **{k: tuple(v) for k, v in json.loads(os.environ.get("TEETER_BOX", "{}")).items()}}


def make_sampler(mode: str, box_scale: float = 1.0, failures_path: str | None = None,
                 failure_frac: float = 0.5, jitter: float = 0.10):
    """Returns f(rng) -> dict of perturbation fields, or None for brain A."""
    box = {k: (lo, lo + (hi - lo) * box_scale) for k, (lo, hi) in TRAIN_BOX.items()}
    axes = list(box)
    lo = np.array([box[a][0] for a in axes]); hi = np.array([box[a][1] for a in axes])

    def uniform(rng):
        return dict(zip(axes, rng.uniform(lo, hi)))

    if mode == "none":
        return None
    if mode == "uniform":
        return uniform
    if mode == "failures":
        pts = json.loads(Path(failures_path).read_text())["failures"]
        if not pts:
            raise ValueError("the failure file holds no failures")
        F = np.array([[p.get(a, 0.0) for a in axes] for p in pts])

        def around(rng):
            base = F[rng.integers(len(F))]
            v = base + rng.normal(0.0, jitter * (hi - lo))
            return dict(zip(axes, np.clip(v, lo, hi)))

        return lambda rng: around(rng) if rng.random() < failure_frac else uniform(rng)
    raise ValueError(f"unknown mode {mode!r}")
