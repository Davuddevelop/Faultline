"""The runner's allowlist: the only robots and policies it will run.

    name: lab-gpu-02            # optional; --name overrides
    max_workers: -1             # cores for one campaign; -1 is all of them
    robots:
      quadruped: ../harness/models/quadruped.xml
    policies:
      stand: stand
      q2-v41: onnx:/srv/policies/q2-walk-v41.onnx

The control plane sends names. A name that is not here is refused, so a
compromised server cannot make this machine load a file or import a module
its owner did not list. Relative paths resolve against this file.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class RunnerConfigError(ValueError):
    pass


@dataclass
class RunnerConfig:
    name: str
    robots: dict[str, Path]
    policies: dict[str, str]
    max_workers: int = -1
    source: Path | None = None
    notes: list[str] = field(default_factory=list)

    def robot_path(self, name: str) -> Path:
        if name not in self.robots:
            raise RunnerConfigError(
                f"robot {name!r} is not in this runner's allowlist ({', '.join(sorted(self.robots)) or 'none'}). "
                f"Add it under 'robots:' in {self.source or 'the runner config'} to allow it")
        return self.robots[name]

    def policy_ref(self, name: str) -> str:
        if name not in self.policies:
            raise RunnerConfigError(
                f"policy {name!r} is not in this runner's allowlist ({', '.join(sorted(self.policies)) or 'none'}). "
                f"Add it under 'policies:' in {self.source or 'the runner config'} to allow it")
        ref = self.policies[name]
        kind, sep, path = ref.partition(":")
        if sep and kind in ("onnx", "torchscript") and not Path(path).is_absolute() and self.source:
            ref = f"{kind}:{(self.source.parent / path).resolve()}"
        return ref


def load(path: str | Path) -> RunnerConfig:
    path = Path(path)
    if not path.exists():
        raise RunnerConfigError(f"no runner config at {path}")
    doc = yaml.safe_load(path.read_text()) or {}
    unknown = set(doc) - {"name", "robots", "policies", "max_workers"}
    if unknown:
        raise RunnerConfigError(f"{path}: unknown key(s) {', '.join(sorted(unknown))}")
    robots: dict[str, Path] = {}
    notes: list[str] = []
    for k, v in (doc.get("robots") or {}).items():
        p = Path(v)
        p = p if p.is_absolute() else (path.parent / p).resolve()
        if not p.exists():
            notes.append(f"robot {k!r}: {p} does not exist; campaigns naming it will fail")
        robots[str(k)] = p
    policies = {str(k): str(v) for k, v in (doc.get("policies") or {}).items()}
    if not robots or not policies:
        raise RunnerConfigError(f"{path}: list at least one robot and one policy; this runner allows nothing")
    return RunnerConfig(name=str(doc.get("name") or socket.gethostname()), robots=robots, policies=policies,
                        max_workers=int(doc.get("max_workers", -1)), source=path.resolve(), notes=notes)
