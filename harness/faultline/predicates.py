"""Evaluating the customer's rules against a trajectory.

Every verdict traces to one predicate and one timestamp. If a run is flagged,
the record says which line flagged it and when, so the customer can disagree
with the rule rather than with us.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .runner import Trajectory
from .spec import Predicate


@dataclass(frozen=True)
class Violation:
    predicate: str
    signal: str
    threshold: float
    op: str
    first_t: float      # when it first fired
    value: float        # the signal's value at that moment
    peak: float         # worst value reached over the whole run

    def as_dict(self) -> dict:
        return {
            "predicate": self.predicate,
            "signal": self.signal,
            "op": self.op,
            "threshold": self.threshold,
            "first_t": round(self.first_t, 6),
            "value_at_first_t": round(self.value, 6),
            "peak": round(self.peak, 6),
        }


def evaluate(traj: Trajectory, predicates: tuple[Predicate, ...]) -> list[Violation]:
    """Check the whole trajectory, not just its final state.

    A policy that breaches a limit at t=3 and recovers by t=6 has still
    breached it, so every step is tested and the first breach is reported.
    """
    out: list[Violation] = []

    for pred in predicates:
        sig = traj.signal(pred.signal)
        fired = (sig > pred.threshold) if pred.op == ">" else (sig < pred.threshold)
        fired &= traj.t >= pred.grace_s

        if not fired.any():
            continue

        idx = int(np.argmax(fired))
        peak = float(sig[traj.t >= pred.grace_s].max() if pred.op == ">"
                     else sig[traj.t >= pred.grace_s].min())
        out.append(
            Violation(
                predicate=pred.name,
                signal=pred.signal,
                threshold=pred.threshold,
                op=pred.op,
                first_t=float(traj.t[idx]),
                value=float(sig[idx]),
                peak=peak,
            )
        )

    out.sort(key=lambda v: v.first_t)
    return out
