"""The gate: did a new checkpoint get worse than its baseline?

Two campaigns are compared only if they ran the same experiment: same robot
(by content hash), same space, rules, search, seeds, duration and layout. Only
the policy may differ. Otherwise the gate is *refused* and says which field
differs; a comparison across a changed space looks meaningful and is not.

Failure modes are matched by what they need (predicate and required axes).
For each mode found by both, the minimal cases are compared axis by axis, in
distance from nominal, with each axis's reduction tolerance as the margin:

  widened     the candidate fails under a smaller condition: worse
  narrowed    the candidate needs a larger condition: better
  unchanged   within tolerance on every axis
  new         found for the candidate, not for the baseline
  not found   found for the baseline, not for the candidate. Not "fixed":
              a search that did not find something has not shown it is gone

The verdict is **blocked** if anything is new or widened, else **passed**.
"""

from __future__ import annotations

from typing import Any

from .contracts import AXES

EXPERIMENT_FIELDS = ("robot", "duration_s", "control_hz", "seeds", "axes", "predicates",
                     "search", "reduce", "bins", "base_body", "observation")


def differences(base: dict[str, Any], cand: dict[str, Any]) -> list[str]:
    """Fields that differ between two finished campaigns' experiments."""
    out = [f for f in EXPERIMENT_FIELDS if base["spec"].get(f) != cand["spec"].get(f)]
    b_robot = (base.get("result") or {}).get("robot", {}).get("sha256")
    c_robot = (cand.get("result") or {}).get("robot", {}).get("sha256")
    if b_robot and c_robot and b_robot != c_robot:
        out.append("robot file (sha256 differs)")
    b_env = (base.get("result") or {}).get("environment")
    c_env = (cand.get("result") or {}).get("environment")
    if b_env and c_env and b_env.get("mujoco") != c_env.get("mujoco"):
        out.append(f"simulator (MuJoCo {b_env.get('mujoco')} against {c_env.get('mujoco')})")
    return out


def _distance(axis: str, value: float, nominals: dict[str, float]) -> float:
    nominal = AXES[axis][1]
    if nominal is None:
        nominal = nominals.get(axis, value)
    return abs(value - nominal)


def compare(base: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    """base and cand: {"spec": ..., "result": ...}, both finished."""
    diff = differences(base, cand)
    if diff:
        return {"verdict": "refused", "differs": diff, "modes": [],
                "reason": "the campaigns ran different experiments, so they cannot be compared: "
                          + ", ".join(diff)}

    def keyed(res: dict[str, Any]) -> dict[tuple[str, tuple[str, ...]], dict[str, Any]]:
        return {(m["predicate"], tuple(sorted(m["required"]))): m for m in res["modes"]}

    b_modes, c_modes = keyed(base["result"]), keyed(cand["result"])
    nominals = {**base["result"].get("nominals", {}), **cand["result"].get("nominals", {})}
    rows = []
    for key in sorted(set(b_modes) | set(c_modes)):
        b, c = b_modes.get(key), c_modes.get(key)
        row: dict[str, Any] = {"predicate": key[0], "required": list(key[1]),
                               "label": (c or b)["label"], "baseline": None, "candidate": None, "axes": []}
        if b:
            row["baseline"] = {a: b["minimal"].get(a) for a in key[1]}
        if c:
            row["candidate"] = {a: c["minimal"].get(a) for a in key[1]}
        if b and c:
            worse = better = False
            for a in key[1]:
                db = _distance(a, float(b["minimal"][a]), nominals)
                dc = _distance(a, float(c["minimal"][a]), nominals)
                tol = AXES[a][2]
                row["axes"].append({"axis": a, "baseline": b["minimal"][a], "candidate": c["minimal"][a],
                                    "tolerance": tol, "unit": AXES[a][0]})
                worse |= dc < db - tol
                better |= dc > db + tol
            row["change"] = "widened" if worse else ("narrowed" if better else "unchanged")
        else:
            row["change"] = "new" if c else "not_found"
        rows.append(row)

    order = {"new": 0, "widened": 1, "unchanged": 2, "narrowed": 3, "not_found": 4}
    rows.sort(key=lambda r: (order[r["change"]], r["label"]))
    blocked = any(r["change"] in ("new", "widened") for r in rows)
    tally = {k: sum(1 for r in rows if r["change"] == k) for k in order}
    return {"verdict": "blocked" if blocked else "passed", "differs": [], "modes": rows, "tally": tally,
            "reason": ("the candidate fails in a way the baseline did not, or under a smaller condition"
                       if blocked else "no failure mode is new or widened against the baseline")}
