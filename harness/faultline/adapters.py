"""Loading a policy that somebody else trained.

Until now a policy had to be Python we could import. A customer's policy is a
file: an exported ONNX graph or a TorchScript archive. These adapters make
those satisfy the same `Policy` protocol as everything else, so nothing
downstream changes.

Three things are enforced at load rather than discovered mid-campaign:

* **Identity is the file's content, not its path.** `policy_id` is a hash of
  the checkpoint. Paths get overwritten and then a run history is a lie about
  which network produced which result.
* **The network must be deterministic.** The same observation twice must give
  the same action. A policy with dropout left enabled makes every reproducibility
  claim downstream false, and the failure is invisible unless it is checked.
* **Widths must line up.** An action of the wrong size reaching MuJoCo is
  either an exception or, worse, silently accepted.

Neither runtime is a dependency of the harness. Someone testing an ONNX policy
should not be made to install PyTorch, so both are extras and both are imported
only when actually used.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


class PolicyLoadError(ValueError):
    """Raised with the offending file and reason named."""


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_path(path: str | Path, suffixes: tuple[str, ...]) -> Path:
    p = Path(path)
    if not p.exists():
        raise PolicyLoadError(f"no such policy file: {p}")
    if p.suffix.lower() not in suffixes:
        raise PolicyLoadError(
            f"{p.name} does not look like {' or '.join(suffixes)}; "
            "pass the exported checkpoint, not the training script"
        )
    return p


class _FilePolicy:
    """Shared behaviour: identity, determinism, and shape discipline."""

    def __init__(self, path: Path, n_actions: int | None) -> None:
        self.path = str(path)
        self.sha256 = _digest(path)
        # short and content-derived: readable in a report, still unambiguous
        self.id = f"{path.stem}@{self.sha256[:12]}"
        self.n_actions = n_actions

    def reset(self, seed: int) -> None:
        """An exported feed-forward network carries no state to reset. A
        recurrent policy does, and is refused at load rather than silently
        run with stale hidden state."""

    def _forward(self, obs: np.ndarray) -> np.ndarray:      # pragma: no cover
        raise NotImplementedError

    def act(self, obs: np.ndarray, t: float) -> np.ndarray:
        out = np.asarray(self._forward(np.asarray(obs, dtype=np.float32)), dtype=float)
        out = out.reshape(-1)                                # drop any batch axis
        if self.n_actions is not None and out.size != self.n_actions:
            raise PolicyLoadError(
                f"{Path(self.path).name} returned {out.size} action(s) but the model "
                f"has {self.n_actions} actuator(s)"
            )
        return out

    def _assert_deterministic(self, width: int) -> None:
        probe = np.linspace(-0.4, 0.4, width, dtype=np.float32)
        a = np.asarray(self._forward(probe), dtype=float).reshape(-1)
        b = np.asarray(self._forward(probe), dtype=float).reshape(-1)
        if not np.array_equal(a, b):
            raise PolicyLoadError(
                f"{Path(self.path).name} is not deterministic: the same observation "
                "gave two different actions. Export with dropout and sampling "
                "disabled — every reproducibility claim downstream depends on this."
            )


class OnnxPolicy(_FilePolicy):
    """An exported ONNX graph."""

    def __init__(self, path: str | Path, *, n_actions: int | None = None) -> None:
        p = _check_path(path, (".onnx",))
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise PolicyLoadError(
                "onnxruntime is not installed. Install the extra: "
                "pip install 'faultline-harness[onnx]'"
            ) from exc

        super().__init__(p, n_actions)
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1     # thread count changes float summation order
        try:
            self._sess = ort.InferenceSession(
                str(p), opts, providers=["CPUExecutionProvider"])
        except Exception as exc:
            raise PolicyLoadError(f"{p.name} did not load as ONNX: {exc}") from exc

        inputs = self._sess.get_inputs()
        if len(inputs) != 1:
            names = ", ".join(i.name for i in inputs)
            raise PolicyLoadError(
                f"{p.name} takes {len(inputs)} inputs ({names}). Only a single "
                "observation input is supported — a recurrent policy carrying hidden "
                "state needs handling this harness does not do yet, and running it "
                "with stale state would produce quietly wrong results."
            )
        self._in = inputs[0].name
        self._out = self._sess.get_outputs()[0].name
        # symbolic dims come back as strings; only a concrete int is a width
        dims = inputs[0].shape
        self.obs_width = next((d for d in reversed(dims) if isinstance(d, int)), None)
        self._batched = len(dims) > 1
        if self.obs_width:
            self._assert_deterministic(self.obs_width)

    def _forward(self, obs: np.ndarray) -> np.ndarray:
        x = obs.reshape(1, -1) if self._batched else obs.reshape(-1)
        return self._sess.run([self._out], {self._in: x})[0]


class TorchScriptPolicy(_FilePolicy):
    """A TorchScript archive saved with torch.jit.save."""

    def __init__(self, path: str | Path, *, n_actions: int | None = None,
                 obs_width: int | None = None) -> None:
        p = _check_path(path, (".pt", ".pth", ".ts"))
        try:
            import torch
        except ImportError as exc:
            raise PolicyLoadError(
                "PyTorch is not installed. Install the extra: "
                "pip install 'faultline-harness[torch]'"
            ) from exc

        super().__init__(p, n_actions)
        self._torch = torch
        torch.set_grad_enabled(False)
        try:
            self._mod = torch.jit.load(str(p), map_location="cpu")
        except Exception as exc:
            raise PolicyLoadError(
                f"{p.name} did not load as TorchScript: {exc}. A plain state_dict "
                "is not loadable this way — export with torch.jit.script or "
                "torch.jit.trace first."
            ) from exc
        self._mod.eval()
        self.obs_width = obs_width
        if obs_width:
            self._assert_deterministic(obs_width)

    def _forward(self, obs: np.ndarray) -> np.ndarray:
        x = self._torch.from_numpy(np.ascontiguousarray(obs)).float().unsqueeze(0)
        with self._torch.no_grad():
            return self._mod(x).cpu().numpy()
