"""The seam where a customer's trained policy plugs in.

Anything with ``reset`` and ``act`` is a policy. The reference implementations
here exist so the harness is testable without a checkpoint; a PPO policy wraps
its forward pass in the same two methods.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np


class Policy(Protocol):
    id: str

    def reset(self, seed: int) -> None: ...

    def act(self, obs: np.ndarray, t: float) -> np.ndarray: ...


class StandPolicy:
    """Holds a nominal stance. Deterministic, and the baseline everything else
    is measured against: if a perturbation does not topple this, it is not
    testing much."""

    def __init__(self, nominal: np.ndarray, name: str = "stand-v1") -> None:
        self._nominal = np.asarray(nominal, dtype=np.float64)
        digest = hashlib.sha256(self._nominal.tobytes()).hexdigest()[:12]
        self.id = f"{name}:{digest}"

    def reset(self, seed: int) -> None:  # nothing stochastic to seed
        return None

    def act(self, obs: np.ndarray, t: float) -> np.ndarray:
        return self._nominal.copy()


class JitterPolicy(StandPolicy):
    """A stochastic policy, present so the determinism tests have something
    that *would* diverge if the policy seed were not honoured."""

    def __init__(self, nominal: np.ndarray, scale: float = 0.02) -> None:
        super().__init__(nominal, name="jitter-v1")
        self._scale = scale
        self._rng = np.random.default_rng(0)
        self.id = f"{self.id}:s{scale}"

    def reset(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def act(self, obs: np.ndarray, t: float) -> np.ndarray:
        return self._nominal + self._rng.normal(0.0, self._scale, self._nominal.shape)
