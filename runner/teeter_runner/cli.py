"""teeter: the command line for people, CI and runners.

    teeter runner start --config runner.yaml       run campaigns on this machine
    teeter campaign run spec.yaml                  plan one, follow it, print what it found
    teeter gate --program P --checkpoint C         CI: exit 0 passed, 1 blocked, 2 refused or error
    teeter status                                  the workspace at a glance

Every command takes --api and --token (or --token-file), or reads TEETER_API
and TEETER_TOKEN from the environment, which is how CI should pass them.
--header adds a header to every request, for a control plane behind an
access proxy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

from .client import ApiError, Client


def _auth(args) -> tuple[str, str]:
    if getattr(args, "header", None):
        # every client this process makes reads them (client.extra_headers)
        os.environ["TEETER_HEADERS"] = "\n".join(filter(None, [os.environ.get("TEETER_HEADERS", ""), *args.header]))
    api = args.api or os.environ.get("TEETER_API")
    token = args.token or os.environ.get("TEETER_TOKEN")
    if not token and args.token_file:
        token = Path(args.token_file).read_text().strip()
    if not api or not token:
        sys.exit("error: give --api and --token (or --token-file), or set TEETER_API and TEETER_TOKEN")
    return api, token


def cmd_runner_start(args) -> int:
    from .agent import Agent
    from .config import RunnerConfigError, load
    api, token = _auth(args)
    try:
        cfg = load(args.config)
    except RunnerConfigError as exc:
        sys.exit(f"error: {exc}")
    return Agent(api, token, cfg, name=args.name, log=lambda m: print(m, flush=True)).run_forever(once=args.once)


def _follow(client: Client, ref: str, quiet: bool = False) -> dict:
    last = None
    while True:
        c = client.get(f"/v1/campaigns/{ref}")
        line = (f"{c['ref']}  {c['state']:<8} {c['progress'].get('phase', ''):<8} "
                f"{c['evaluations']}/{c['budget']} evaluations, {c['failures']} violation(s)")
        if not quiet and line != last:
            print(line, flush=True)
            last = line
        if c["state"] in ("done", "failed", "canceled"):
            return c
        time.sleep(1.0)


def cmd_campaign_run(args) -> int:
    api, token = _auth(args)
    text = Path(args.spec).read_text()
    spec = json.loads(text) if args.spec.endswith(".json") else yaml.safe_load(text)
    client = Client(api, token)
    try:
        c = client.post("/v1/campaigns", {"spec": spec})
    except ApiError as exc:
        sys.exit(f"error: {exc.message}")
    print(f"{c['ref']} queued: {spec.get('robot')} / {spec.get('policy')}")
    if not args.wait:
        return 0
    c = _follow(client, c["ref"])
    if c["state"] != "done":
        print(f"{c['ref']} {c['state']}: {c.get('error') or ''}")
        return 2
    for m in c["modes"]:
        mins = ", ".join(f"{a} {m['minimal'][a]:g}" for a in m["required"])
        print(f"  {m['count']:>3} x  {m['label']}   minimal: {mins}   first breach {m['first_t']:.2f} s")
    if not c["modes"]:
        print("no violations found. That bounds nothing: this budget, in this space, did not find one.")
    return 1 if c["failures"] else 0


def cmd_gate(args) -> int:
    api, token = _auth(args)
    client = Client(api, token)
    try:
        g = client.post(f"/v1/programs/{args.program}/gate", {"checkpoint": args.checkpoint})
    except ApiError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 2
    print(f"{g['ref']}: {args.checkpoint} ({g['candidate']['ref']}) against the baseline "
          f"{g['baseline']['policy']} ({g['baseline']['ref']})", flush=True)
    deadline = time.monotonic() + args.timeout
    while g["state"] != "decided":
        if time.monotonic() > deadline:
            print(f"error: no verdict after {args.timeout:.0f} s; is a runner online for this program?",
                  file=sys.stderr)
            return 2
        time.sleep(2.0)
        g = client.get(f"/v1/gates/{g['ref']}")
    comp = g["comparison"]
    print(f"\n{g['verdict'].upper()}: {comp['reason']}")
    for m in comp.get("modes", []):
        axes = "; ".join(f"{a['axis']} {a['baseline']:g} -> {a['candidate']:g}" for a in m.get("axes", []))
        print(f"  {m['change']:<10} {m['label']}{'   ' + axes if axes else ''}")
    return {"passed": 0, "blocked": 1}.get(g["verdict"], 2)


def cmd_status(args) -> int:
    api, token = _auth(args)
    client = Client(api, token)
    me, ov = client.get("/v1/me"), client.get("/v1/overview")
    print(f"{me['workspace']['name']} ({me['workspace']['slug']}) at {api}")
    print(f"  runners   {ov['runners']['online']} of {ov['runners']['total']} online")
    print(f"  campaigns {', '.join(f'{v} {k}' for k, v in ov['campaigns'].items()) or 'none'}")
    print(f"  gates     {', '.join(f'{v} {k}' for k, v in ov['gates'].items()) or 'none'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="teeter", description="Teeter: test learned robot policies on your machines.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api", help="control plane URL (or TEETER_API)")
    common.add_argument("--token", help="token (or TEETER_TOKEN)")
    common.add_argument("--token-file", help="read the token from a file")
    common.add_argument("--header", action="append", metavar="'NAME: VALUE'",
                        help="send this header with every request too, for a control plane behind an "
                             "access proxy (repeatable; or TEETER_HEADERS, one per line)")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("runner", help="run campaigns on this machine")
    rs = r.add_subparsers(dest="sub", required=True)
    start = rs.add_parser("start", parents=[common], help="register and run jobs until stopped")
    start.add_argument("--config", required=True, help="the runner's allowlist (YAML)")
    start.add_argument("--name", help="how this machine appears on the Runners page")
    start.add_argument("--once", action="store_true", help="run at most one job, then exit")
    start.set_defaults(func=cmd_runner_start)

    c = sub.add_parser("campaign", help="plan and follow campaigns")
    cs = c.add_subparsers(dest="sub", required=True)
    run = cs.add_parser("run", parents=[common], help="queue a campaign spec and follow it")
    run.add_argument("spec", help="a teeter.campaign/1 spec, YAML or JSON")
    run.add_argument("--no-wait", dest="wait", action="store_false", help="queue it and return")
    run.set_defaults(func=cmd_campaign_run)

    g = sub.add_parser("gate", parents=[common], help="gate a checkpoint against its program's baseline")
    g.add_argument("--program", required=True)
    g.add_argument("--checkpoint", required=True)
    g.add_argument("--timeout", type=float, default=3600.0, help="seconds to wait for a verdict")
    g.set_defaults(func=cmd_gate)

    s = sub.add_parser("status", parents=[common], help="the workspace at a glance")
    s.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except ApiError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
