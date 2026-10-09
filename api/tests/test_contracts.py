"""The API restates the engine's axis table and signal list so it can run
without MuJoCo. These tests import the engine and hold the two together."""

from __future__ import annotations

import pytest

from teeter_api.contracts import AXES, SIGNALS, CampaignSpec

faultline = pytest.importorskip("faultline", reason="the engine is not installed beside the API")


def test_axes_are_the_engines():
    from faultline.reduce import SEVERITY_AXES
    assert list(AXES) == [a.field for a in SEVERITY_AXES]
    for a in SEVERITY_AXES:
        unit, nominal, tol, _ = AXES[a.field]
        assert (unit, nominal, tol) == (a.unit, a.nominal, a.tolerance)


def test_signals_are_the_trajectorys():
    from faultline.runner import Trajectory
    assert list(SIGNALS) == [f for f in Trajectory.__dataclass_fields__ if f != "t"]


def test_the_axes_the_runner_quantises_are_flagged():
    from faultline.spec import Perturbation   # noqa: F401  the fields exist
    assert {k for k, v in AXES.items() if v[3]} == {"push_impulse_ns", "sensor_lag_ms"}


def test_the_experiment_hash_ignores_only_the_policy():
    base = dict(robot="quadruped", policy="stand", axes={"push_impulse_ns": (0, 9)},
                predicates=[{"name": "t", "signal": "tilt_deg", "op": ">", "threshold": 35}])
    a, b = CampaignSpec(**base), CampaignSpec(**{**base, "policy": "tall"})
    c = CampaignSpec(**{**base, "duration_s": 6})
    assert a.experiment_sha256() == b.experiment_sha256() != c.experiment_sha256()
