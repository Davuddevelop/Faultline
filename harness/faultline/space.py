"""The volume a campaign searches.

The customer declares the axes and their bounds; we search the box they
enclose. Bounds are in physical units for the same reason perturbations are —
an assessor needs to read what was covered, not a normalised cube.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .reduce import SEVERITY_AXES

_AXIS_BY_NAME = {a.field: a for a in SEVERITY_AXES}


@dataclass(frozen=True)
class SearchSpace:
    """Per-axis inclusive bounds. Only the axes with a magnitude are
    searchable; `push_time_s` and the yaw fields describe *when* and *which
    way*, and are set on the base spec instead."""

    bounds: Mapping[str, tuple[float, float]]

    def __post_init__(self) -> None:
        if not self.bounds:
            raise ValueError("a search space needs at least one axis")
        for name, pair in self.bounds.items():
            if name not in _AXIS_BY_NAME:
                raise ValueError(
                    f"{name!r} is not a searchable axis; available: "
                    + ", ".join(sorted(_AXIS_BY_NAME))
                )
            lo, hi = pair
            if not hi > lo:
                raise ValueError(f"{name}: upper bound must exceed lower, got ({lo}, {hi})")
        object.__setattr__(self, "bounds", dict(self.bounds))

    @property
    def axes(self) -> tuple[str, ...]:
        return tuple(self.bounds)                 # insertion order, stable

    @property
    def dims(self) -> int:
        return len(self.bounds)

    def lo(self) -> np.ndarray:
        return np.array([self.bounds[a][0] for a in self.axes], dtype=np.float64)

    def hi(self) -> np.ndarray:
        return np.array([self.bounds[a][1] for a in self.axes], dtype=np.float64)

    def sample(self, rng: np.random.Generator) -> dict[str, float]:
        """One uniform point in the box."""
        return self.to_kwargs(rng.uniform(self.lo(), self.hi()))

    def clip(self, values: np.ndarray) -> np.ndarray:
        return np.clip(values, self.lo(), self.hi())

    def to_kwargs(self, values: np.ndarray) -> dict[str, float]:
        return {a: float(v) for a, v in zip(self.axes, values)}

    def unit(self, axis: str) -> str:
        return _AXIS_BY_NAME[axis].unit

    def as_dict(self) -> dict[str, Any]:
        return {a: list(self.bounds[a]) for a in self.axes}
