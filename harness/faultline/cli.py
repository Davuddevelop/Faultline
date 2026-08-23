"""The command line.

Argument parsing, progress and exit codes over the pipeline that already
exists. Deliberately holds no logic of its own: if something here decided how
a campaign runs, there would be two answers to that question.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from . import __version__
from .config import Campaign, ConfigError, load
from .record import replay as replay_record
from .report import build_report, write_deliverables
from .search import cem_search, random_search

STARTER = """\
# A Faultline campaign. Everything here is yours to change.
#
#   faultline run campaign.yaml
#
# The simulator version is not set here on purpose: it is recorded with every
# run rather than chosen, so a result can be re-executed against the physics
# that produced it.

robot: {robot}

# "stand" is the built-in baseline that holds a stance. Point this at your own
# policy as "module:Attr" — anything with reset(seed) and act(obs, t).
policy: stand

duration_s: 5.0

# Three seeds, not one. A single global seed hides which component caused a
# divergence when a replay does not match.
seeds:
  sampler: 0xA13F
  sim: 0
  policy: 0

# The volume to search, in physical units. Ranges are yours.
axes:
  push_impulse_ns: [0, 9]       # N.s
  slope_deg:       [0, 10]      # degrees
  sensor_lag_ms:   [0, 60]      # milliseconds
  torque_loss_pct: [0, 15]      # percent
  payload_kg:      [0, 2.0]     # kilograms

# What counts as a failure. Rules you wrote, checked over the whole
# trajectory — never a learned classifier.
predicates:
  - {{name: tilt_limit, signal: tilt_deg,  op: ">", threshold: 35.0, grace_s: 0.3}}
  - {{name: fallen,     signal: height_m,  op: "<", threshold: 0.12, grace_s: 0.3}}

search:
  method: cem                   # cem (directed) or random
  budget: 120                   # simulations

reduce:
  enabled: true
  max: 10                       # minimise the N most severe failures
  budget: 200

report:
  out: deliverables
"""


def _default_model() -> Path:
    return (Path(__file__).resolve().parents[1] / "models" / "quadruped.xml")


def cmd_init(args: argparse.Namespace) -> int:
    out = Path(args.path)
    if out.exists() and not args.force:
        print(f"{out} already exists (use --force to overwrite)", file=sys.stderr)
        return 2
    model = Path(args.robot) if args.robot else _default_model()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(STARTER.format(robot=model))
    print(f"wrote {out}")
    print(f"  next: faultline run {out}")
    return 0


def _run_campaign(c: Campaign, quiet: bool = False) -> tuple[int, Path | None]:
    policy = c.policy()
    search = cem_search if c.method == "cem" else random_search

    if not quiet:
        print(f"campaign  {c.source}")
        print(f"  robot     {c.spec.model_path}")
        print(f"  policy    {c.policy_ref}")
        print(f"  space     {c.space.dims} axes")
        print(f"  search    {c.method}, {c.budget} simulations")

    campaign = search(c.spec, policy, c.space, budget=c.budget,
                      seed=c.spec.seeds.sampler, target_predicate=c.target)
    if not quiet:
        print(f"\n{campaign.summary()}")

    if not campaign.failures:
        if not quiet:
            print("\nNo violations found. That bounds nothing: it means this budget, "
                  "in this space, did not find one.")
        return 0, None

    report = build_report(campaign, c.spec, policy,
                          max_reduce=c.reduce_max if c.reduce_enabled else 1,
                          reduce_budget=c.reduce_budget, bins=c.bins)
    if not quiet:
        print(f"\n{len(report.modes)} failure mode(s) from the "
              f"{report.reduced_count} most severe of {report.failures_total}:")
        for i, m in enumerate(report.modes, 1):
            print(f"  {i}. {len(m.members):>2} x  {m.label}")
        cov = report.coverage
        print(f"\ncoverage  {cov.cells_visited}/{cov.cells_total} cells "
              f"({cov.fraction:.2%}) at {cov.bins} bins per axis")

    out = write_deliverables(report, policy, c.out_dir)
    if not quiet:
        print(f"\nwritten to {out}")
        for f in sorted(out.rglob("*")):
            if f.is_file():
                print(f"  {f.relative_to(out)}")
    return 1, out


def cmd_run(args: argparse.Namespace) -> int:
    campaign = load(args.config)
    if args.budget:
        campaign.budget = args.budget
    if args.out:
        campaign.out_dir = Path(args.out)
    code, _ = _run_campaign(campaign, quiet=args.quiet)
    return code


def cmd_replay(args: argparse.Namespace) -> int:
    import json

    doc = json.loads(Path(args.record).read_text())
    from .config import load_policy

    policy = load_policy(args.policy, doc["spec"]["model_path"])
    result = replay_record(args.record, policy)

    print("matched" if result.matched else "DIVERGED")
    print(f"  expected  {result.expected_digest[:32]}")
    print(f"  actual    {result.actual_digest[:32]}")
    for note in result.notes:
        print(f"  note: {note}")
    return 0 if result.matched else 1


def cmd_version(args: argparse.Namespace) -> int:
    import mujoco
    import numpy

    print(f"faultline {__version__}")
    print(f"  mujoco   {mujoco.__version__}")
    print(f"  numpy    {numpy.__version__}")
    print(f"  python   {platform.python_version()}")
    print(f"  platform {platform.system()}-{platform.machine()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="faultline",
        description="Adversarial testing for learned robot control policies.",
        epilog="Exit code 1 means violations were found, 0 means none were.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    i = sub.add_parser("init", help="write a starter campaign.yaml")
    i.add_argument("path", nargs="?", default="campaign.yaml")
    i.add_argument("--robot", help="path to a URDF or MJCF (defaults to the bundled quadruped)")
    i.add_argument("--force", action="store_true", help="overwrite an existing file")
    i.set_defaults(func=cmd_init)

    r = sub.add_parser("run", help="search, reduce, and write the deliverables")
    r.add_argument("config", nargs="?", default="campaign.yaml")
    r.add_argument("--budget", type=int, help="override the simulation budget")
    r.add_argument("--out", help="override the output directory")
    r.add_argument("-q", "--quiet", action="store_true")
    r.set_defaults(func=cmd_run)

    p2 = sub.add_parser("replay", help="re-execute a recorded run and check it matches")
    p2.add_argument("record", help="path to a run record JSON")
    p2.add_argument("--policy", default="stand", help="module:Attr, or 'stand'")
    p2.set_defaults(func=cmd_replay)

    v = sub.add_parser("version", help="versions of everything that affects a result")
    v.set_defaults(func=cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
