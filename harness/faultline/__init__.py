"""Faultline harness — deterministic evaluation of learned robot policies.

One run, reproducible from its record. Search, minimisation and reporting are
built on top of this and are deliberately not part of it.
"""

from .policies import JitterPolicy, Policy, StandPolicy
from .predicates import Violation, evaluate
from .record import ReplayResult, RunRecord, execute, replay
from .runner import Trajectory, run, sim_environment
from .spec import Perturbation, Predicate, RunSpec, Seeds

__all__ = [
    "Perturbation", "Predicate", "RunSpec", "Seeds",
    "Policy", "StandPolicy", "JitterPolicy",
    "Trajectory", "run", "sim_environment",
    "Violation", "evaluate",
    "RunRecord", "ReplayResult", "execute", "replay",
]
__version__ = "0.1.0"
