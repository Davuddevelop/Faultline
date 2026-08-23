"""Reading a campaign from YAML.

This is the file that makes `campaign.yaml` real. It introduces no new domain
concepts — every key maps onto an object that already exists, and validation
is delegated to those objects so there is exactly one definition of what a
valid axis or predicate is.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .policies import Policy, StandPolicy
from .space import SearchSpace
from .spec import Predicate, RunSpec, Seeds

TOP_LEVEL = {
    "robot", "policy", "duration_s", "control_hz", "seeds",
    "axes", "predicates", "search", "reduce", "report",
}
SEARCH_KEYS = {"method", "budget", "target"}
REDUCE_KEYS = {"enabled", "max", "budget"}
REPORT_KEYS = {"out", "bins"}


class ConfigError(ValueError):
    """Raised with the offending field named, rather than a stack trace."""


def _require(doc: dict, key: str, path: Path) -> Any:
    if key not in doc:
        raise ConfigError(f"{path}: missing required key {key!r}")
    return doc[key]


def _check_keys(got: Any, allowed: set[str], where: str, path: Path) -> dict:
    if not isinstance(got, dict):
        raise ConfigError(f"{path}: {where} must be a mapping, got {type(got).__name__}")
    unknown = set(got) - allowed
    if unknown:
        raise ConfigError(
            f"{path}: unknown key(s) in {where}: {', '.join(sorted(unknown))}; "
            f"allowed: {', '.join(sorted(allowed))}"
        )
    return got


def load_policy(ref: str, model_path: str) -> Policy:
    """``module:Attr``, or ``stand`` for the built-in baseline.

    The baseline exists so the quickstart runs before the reader has written
    any code of their own.
    """
    if ref == "stand":
        import mujoco

        return StandPolicy(mujoco.MjModel.from_xml_path(model_path).key_ctrl[0])

    if ":" not in ref:
        raise ConfigError(
            f"policy {ref!r} must be 'module:Attr' (or 'stand' for the baseline)"
        )
    module_name, attr = ref.split(":", 1)
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ConfigError(f"cannot import policy module {module_name!r}: {exc}") from exc
    try:
        obj = getattr(module, attr)
    except AttributeError as exc:
        raise ConfigError(f"module {module_name!r} has no attribute {attr!r}") from exc

    policy = obj() if isinstance(obj, type) else obj
    for method in ("reset", "act"):
        if not callable(getattr(policy, method, None)):
            raise ConfigError(f"policy {ref!r} has no callable {method}()")
    return policy


@dataclass
class Campaign:
    """Everything one `faultline run` needs."""

    spec: RunSpec
    space: SearchSpace
    policy_ref: str
    method: str
    budget: int
    target: str | None
    reduce_enabled: bool
    reduce_max: int
    reduce_budget: int
    out_dir: Path
    bins: int
    source: Path

    def policy(self) -> Policy:
        return load_policy(self.policy_ref, self.spec.model_path)


def load(path: str | Path) -> Campaign:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"no such config: {path}")

    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: not valid YAML — {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")
    _check_keys(doc, TOP_LEVEL, "the top level", path)

    robot = Path(_require(doc, "robot", path))
    if not robot.is_absolute():
        robot = (path.parent / robot).resolve()
    if not robot.exists():
        raise ConfigError(f"{path}: robot model not found: {robot}")

    seeds_raw = _check_keys(doc.get("seeds", {}), {"sampler", "sim", "policy"}, "seeds", path)
    seeds = Seeds(**{k: int(v) for k, v in seeds_raw.items()})

    preds = []
    for i, p in enumerate(doc.get("predicates") or []):
        if not isinstance(p, dict):
            raise ConfigError(f"{path}: predicates[{i}] must be a mapping")
        try:
            preds.append(Predicate(**p))          # Predicate validates op and grace
        except TypeError as exc:
            raise ConfigError(f"{path}: predicates[{i}]: {exc}") from exc
        except ValueError as exc:
            raise ConfigError(f"{path}: predicates[{i}]: {exc}") from exc
    if not preds:
        raise ConfigError(f"{path}: at least one predicate is required — "
                          "without one nothing can be flagged")

    axes = doc.get("axes") or {}
    if not isinstance(axes, dict) or not axes:
        raise ConfigError(f"{path}: 'axes' must be a non-empty mapping of axis -> [lo, hi]")
    bounds = {}
    for name, pair in axes.items():
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            raise ConfigError(f"{path}: axes.{name} must be [lo, hi], got {pair!r}")
        bounds[name] = (float(pair[0]), float(pair[1]))
    try:
        space = SearchSpace(bounds)               # SearchSpace validates names and order
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc

    search = _check_keys(doc.get("search", {}), SEARCH_KEYS, "search", path)
    method = str(search.get("method", "cem"))
    if method not in ("cem", "random"):
        raise ConfigError(f"{path}: search.method must be 'cem' or 'random', got {method!r}")
    budget = int(search.get("budget", 150))
    target = search.get("target")
    if target is not None and target not in {p.name for p in preds}:
        raise ConfigError(
            f"{path}: search.target {target!r} is not a declared predicate; "
            f"declared: {', '.join(p.name for p in preds)}"
        )

    reduce_cfg = _check_keys(doc.get("reduce", {}), REDUCE_KEYS, "reduce", path)
    report_cfg = _check_keys(doc.get("report", {}), REPORT_KEYS, "report", path)

    spec = RunSpec(
        model_path=str(robot),
        policy_id=str(_require(doc, "policy", path)),
        predicates=tuple(preds),
        seeds=seeds,
        duration_s=float(doc.get("duration_s", 5.0)),
        control_hz=float(doc.get("control_hz", 50.0)),
    )

    out = Path(report_cfg.get("out", "deliverables"))
    if not out.is_absolute():
        out = path.parent / out

    return Campaign(
        spec=spec, space=space, policy_ref=str(doc["policy"]),
        method=method, budget=budget, target=target,
        reduce_enabled=bool(reduce_cfg.get("enabled", True)),
        reduce_max=int(reduce_cfg.get("max", 10)),
        reduce_budget=int(reduce_cfg.get("budget", 200)),
        out_dir=out, bins=int(report_cfg.get("bins", 4)), source=path,
    )
