#!/usr/bin/env python3
"""Write the data the product prototype at teeter/app/ is drawn from.

The prototype shows two kinds of data, and says which on every panel:

  record    read here from the published campaign and the harness itself:
            assets/data/campaign.json, media/sim.json, the robot model, the
            axis table, the trajectory signals, the default observation layout
  example   illustrative workspaces, checkpoints, runners and people, written
            by hand in teeter/app/js/example.js and labelled on screen

This script writes only the first, to teeter/app/js/record.js. It reads the
harness's source rather than importing it, so it runs without MuJoCo;
harness/tests/test_teeter_app.py imports the harness and holds the file to it.

    python3 tools/build_teeter_app.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_teeter_site as site     # noqa: E402

ROOT = site.ROOT
HARNESS = ROOT / "harness"
OUT = ROOT / "teeter" / "app" / "js" / "record.js"
MODEL = HARNESS / "models" / "quadruped.xml"


def axes():
    """The searchable axes, from SEVERITY_AXES in reduce.py: the table
    space._AXIS_BY_NAME is built from."""
    src = (HARNESS / "faultline" / "reduce.py").read_text()
    block = src[src.index("SEVERITY_AXES: tuple[Axis, ...] = ("):]
    block = block[:block.index("\n)\n")]
    out = []
    for name, nominal, tol, unit in re.findall(r'Axis\("(\w+)", ([\w.]+), ([\d.]+), "([^"]+)"\)', block):
        out.append({"name": name, "nominal": None if nominal == "None" else float(nominal),
                    "tolerance": float(tol), "unit": unit})
    return out


def signals():
    """The fields of Trajectory other than time: all a predicate can see."""
    src = (HARNESS / "faultline" / "runner.py").read_text()
    block = src[src.index("class Trajectory:"):]
    block = block[:block.index("def signal")]
    return [n for n in re.findall(r"^    (\w+): np\.ndarray", block, re.M) if n != "t"]


def robot():
    """What the harness reads from the model, read the same way."""
    raw = MODEL.read_bytes()
    tree = ET.fromstring(raw)
    joints = [j.get("name") for j in tree.iter("joint") if j.get("name")]
    actuators = [{"name": a.get("name"), "joint": a.get("joint"), "type": a.tag}
                 for a in tree.find("actuator")]
    bodies = [b.get("name") for b in tree.iter("body")]
    free = [b.get("name") for b in tree.iter("body") if b.find("freejoint") is not None]
    opt = tree.find("option")
    default_pos = tree.find("default").find("position")
    ranges = {j.get("name"): [float(v) for v in j.get("range").split()]
              for j in tree.iter("joint") if j.get("name") and j.get("range")}
    return {
        "file": "harness/models/quadruped.xml", "format": "MJCF",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "joints": joints, "ranges": ranges, "actuators": actuators,
        "bodies": len(bodies) + 1,                 # MuJoCo counts the world body
        "free_base": free[0] if free else None,
        "timestep": float(opt.get("timestep")), "solver": opt.get("solver"),
        "integrator": opt.get("integrator"), "iterations": int(opt.get("iterations")),
        "kp": float(default_pos.get("kp")), "forcerange": default_pos.get("forcerange"),
        "keyframe": tree.find("keyframe") is not None,
        "half": site.torso_half_extents(),
    }


def layout(n_joints, n_actuators):
    """ObservationSpec.default(), with each term's width for this robot."""
    src = (HARNESS / "faultline" / "observe.py").read_text()
    block = src[src.index("def default()"):]
    block = block[:block.index("def raw()")]
    widths = {"projected_gravity": 3, "base_ang_vel": 3, "base_lin_vel": 3, "base_quat": 4,
              "joint_pos": n_joints, "joint_vel": n_joints, "prev_action": n_actuators}
    out, at = [], 0
    for kind, args in re.findall(r'Term\("(\w+)"(?:, ([^)]*))?\)', block):
        scale = re.search(r"scale=([\d.]+)", args or "")
        w = widths[kind]
        out.append({"kind": kind, "from": at, "to": at + w, "scale": float(scale.group(1)) if scale else 1.0,
                    "relative": "relative=True" in (args or "")})
        at += w
    return out


def control_hz():
    src = (HARNESS / "faultline" / "config.py").read_text()
    return float(re.search(r'control_hz=float\(doc\.get\("control_hz", ([\d.]+)\)\)', src).group(1))


def cli_commands():
    src = (HARNESS / "faultline" / "cli.py").read_text()
    return [{"name": n, "help": h} for n, h in re.findall(r'add_parser\("(\w+)", help="([^"]+)"\)', src)]


def harness_version():
    src = (HARNESS / "faultline" / "__init__.py").read_text()
    return re.search(r'__version__ = "([^"]+)"', src).group(1)


def build():
    c = json.loads((ROOT / "assets/data/campaign.json").read_text())
    s = json.loads((ROOT / "media/sim.json").read_text())
    rb = robot()
    lay = layout(len(rb["joints"]), len(rb["actuators"]))
    vals = site.site_values(c, s)
    replay = site.replay_json(s, c, site.REPLAY_SPEED)
    replay = json.loads(replay[replay.index(">") + 1:replay.rindex("</script>")])
    doc = {
        "source": "assets/data/campaign.json, media/sim.json, harness/",
        "harness": harness_version(),
        "campaign": {k: c[k] for k in ("generated", "budget", "seeds", "space", "totals",
                                        "first_failure", "efficiency", "scatter")},
        "report": c["report"],
        "values": vals,
        "axes": axes(),
        "signals": signals(),
        "robot": rb,
        "layout": lay,
        "control_hz": control_hz(),
        "commands": cli_commands(),
        "yaml": site.campaign_yaml(c, markup=False),
        "nominal_tilt": s["runs"]["nominal"]["tilt"],
        "minimal_tilt": s["runs"]["minimal"]["tilt"],
        "hz": s["hz"],
        "brand": {"lockup": site.bb.inline(*site.bb.lockup("app")),
                  "mark": site.bb.inline("0 0 32 32", site.bb.mark_b("appm", box=32)),
                  "mark2": site.bb.inline("0 0 32 32", site.bb.mark_b("appm2", box=32))},
    }
    return ("/* Generated by tools/build_teeter_app.py from the published campaign record\n"
            "   and the harness source. Do not edit; run the builder. */\n"
            "window.TEETER_RECORD = " + json.dumps(doc, separators=(",", ":"), ensure_ascii=False) + ";\n"
            "window.TEETER_REPLAY = " + json.dumps(replay, separators=(",", ":")) + ";\n")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build())
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
