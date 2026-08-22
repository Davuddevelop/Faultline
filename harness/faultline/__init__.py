"""Faultline harness — deterministic evaluation of learned robot policies.

One run, reproducible from its record. Search, minimisation and reporting are
built on top of this and are deliberately not part of it.
"""

from .policies import JitterPolicy, Policy, StandPolicy
from .predicates import Violation, evaluate, severity
from .record import ReplayResult, RunRecord, execute, replay
from .reduce import (
    SEVERITY_AXES, Axis, AxisOutcome, ReductionError, ReductionResult,
    reduce_failure,
)
from .runner import Trajectory, run, sim_environment
from .search import (
    METHODS, CampaignResult, ComparisonResult, Sample,
    cem_search, compare, random_search,
)
from .report import (
    Coverage, FailureMode, Report, build_report, engineering_report,
    measure_coverage, safety_appendix, write_archive, write_deliverables,
)
from .space import SearchSpace
from .spec import Perturbation, Predicate, RunSpec, Seeds

__all__ = [
    "Perturbation", "Predicate", "RunSpec", "Seeds",
    "Policy", "StandPolicy", "JitterPolicy",
    "Trajectory", "run", "sim_environment",
    "Violation", "evaluate", "severity",
    "SearchSpace", "Sample", "CampaignResult", "ComparisonResult",
    "random_search", "cem_search", "compare", "METHODS",
    "Report", "FailureMode", "Coverage", "build_report",
    "measure_coverage", "engineering_report", "safety_appendix",
    "write_archive", "write_deliverables",
    "RunRecord", "ReplayResult", "execute", "replay",
    "reduce_failure", "ReductionResult", "ReductionError",
    "Axis", "AxisOutcome", "SEVERITY_AXES",
]
__version__ = "0.1.0"
