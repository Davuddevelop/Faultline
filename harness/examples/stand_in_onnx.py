"""A stand-in for an exported policy: a small random network, NOT a trained one.

    pip install onnx                      # only this script needs it
    python examples/stand_in_onnx.py my-policy.onnx 0

It reads the 30-wide observation the walkthrough's campaign builds
(projected gravity, base angular velocity, joint positions relative to the
stance, scaled joint velocities) and returns 12 joint targets: the stance plus
a small correction, the shape many legged policies are exported in. Its
weights come from the seed; it exists so the ONNX path can be tried before a
real checkpoint is to hand.
"""

from __future__ import annotations

import sys

import numpy as np
import onnx
from onnx import TensorProto, helper

out = sys.argv[1] if len(sys.argv) > 1 else "my-policy.onnx"
rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
W1 = (rng.standard_normal((30, 16)) * 0.3).astype(np.float32)
W2 = (rng.standard_normal((16, 12)) * 0.3).astype(np.float32)
scale = np.full(12, 0.1, np.float32)
stance = np.array([0, 0.75, -1.5] * 4, np.float32)      # the quadruped's keyframe

g = helper.make_graph(
    [helper.make_node("MatMul", ["obs", "W1"], ["h"]), helper.make_node("Tanh", ["h"], ["a"]),
     helper.make_node("MatMul", ["a", "W2"], ["d"]), helper.make_node("Mul", ["d", "scale"], ["ds"]),
     helper.make_node("Add", ["ds", "stance"], ["action"])],
    "policy",
    [helper.make_tensor_value_info("obs", TensorProto.FLOAT, ["batch", 30])],
    [helper.make_tensor_value_info("action", TensorProto.FLOAT, ["batch", 12])],
    [helper.make_tensor(n, TensorProto.FLOAT, v.shape, v.ravel()) for n, v in
     [("W1", W1), ("W2", W2), ("scale", scale), ("stance", stance)]])
m = helper.make_model(g, opset_imports=[helper.make_opsetid("", 13)])
m.ir_version = 10
onnx.save(m, out)
print("wrote", out)
