"""teeter-api: run and administer a control plane.

    teeter-api serve [--host H] [--port P]      migrate, then serve the API and the app at /app/
    teeter-api migrate                          bring the database to the latest schema
    teeter-api demo                             a demo workspace, program and runner token
    teeter-api link   --workspace W --email E   a one-time sign-in link
    teeter-api member --workspace W --email E   add someone to a workspace (an invitation)
    teeter-api token  --workspace W --kind K    a new token, printed once

Every command reads its database from the environment (settings.py), so the
same commands administer a laptop's SQLite file and the hosted Postgres.
"""

from __future__ import annotations

import argparse
import secrets
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from .db import Database, utcnow
from .models import ROLES, Checkpoint, Membership, Program, SignInLink, Token, User, Workspace
from .security import digest, mint
from .settings import get_settings

# The demo program: the published campaign's experiment on the stand-in
# quadruped, smaller so it finishes in under a minute on a laptop. The three
# checkpoints are poses held still, not trained policies (see
# runner/teeter_runner/demo_policies.py), and the app says so.
DEMO_SPEC = {
    "robot": "quadruped",
    "duration_s": 5.0,
    "seeds": {"sampler": 0, "sim": 0, "policy": 0},
    "axes": {"push_impulse_ns": [0.0, 9.0], "slope_deg": [0.0, 10.0], "sensor_lag_ms": [0.0, 60.0],
             "torque_loss_pct": [0.0, 15.0], "payload_kg": [0.0, 2.0], "payload_offset_m": [0.0, 0.06]},
    "predicates": [
        {"name": "tilt_limit", "signal": "tilt_deg", "op": ">", "threshold": 35.0, "grace_s": 0.3},
        {"name": "fallen", "signal": "height_m", "op": "<", "threshold": 0.12, "grace_s": 0.3},
    ],
    "search": {"method": "cem", "budget": 150, "workers": -1},
    "reduce": {"enabled": True, "max": 5, "budget": 200},
}
DEMO_CHECKPOINTS = (
    ("stand-v1", "stand", "The harness's built-in stance: holds the model's keyframe pose.", True),
    ("tall-v2", "tall", "Demo pose, legs straighter than stand-v1. Held still; not a trained policy.", False),
    ("crouch-v3", "crouch", "Demo pose, legs bent more than stand-v1. Held still; not a trained policy.", False),
)


def _db() -> Database:
    """The configured database, migrated to the latest schema."""
    settings = get_settings()
    db = Database(settings.database_url, pool_size=2, direct_url=settings.database_url_direct)
    try:
        db.migrate()
    except RuntimeError as exc:
        sys.exit(f"error: {exc}")
    return db


def _where(db: Database) -> str:
    return db.engine.url.render_as_string(hide_password=True)


def _workspace(session, slug: str) -> Workspace:
    ws = session.scalar(select(Workspace).where(Workspace.slug == slug))
    if ws is None:
        sys.exit(f"no workspace {slug!r}; create one with 'teeter-api demo'")
    return ws


def _link(session, ws: Workspace, user: User, minutes: int = 30) -> str:
    code = secrets.token_urlsafe(24)
    session.add(SignInLink(code_sha256=digest(code), workspace_id=ws.id, user_id=user.id,
                           expires_at=utcnow() + timedelta(minutes=minutes)))
    session.commit()
    return f"{get_settings().public_url.rstrip('/')}/v1/auth/link/{code}"


def _token_file(session, ws: Workspace, kind: str, name: str, path: Path) -> Path:
    """Keep the token already in ``path`` if this database still honours it,
    otherwise mint one and write it there. Running the demo again must not
    strand a runner that registered with the first token."""
    if path.exists():
        tok = session.scalar(select(Token).where(Token.secret_sha256 == digest(path.read_text().strip())))
        if tok is not None and tok.workspace_id == ws.id and tok.kind == kind and tok.revoked_at is None:
            return path
    _, secret = mint(session, ws, kind, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(secret + "\n")
    path.chmod(0o600)
    return path


def _shown(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def cmd_serve(args) -> int:
    import uvicorn
    if not args.no_migrate:
        db = _db()
        print(f"schema at {db.revision()} in {_where(db)}", flush=True)
        db.engine.dispose()
    # A runner's claim is a long-poll of up to 25 s; on shutdown, give open
    # requests 5 s and then drop them. A claim dropped after it committed is
    # not lost: its lease lapses and the job is claimed again.
    uvicorn.run("teeter_api.app:create_app", factory=True, host=args.host, port=args.port,
                log_level="info", proxy_headers=True, timeout_graceful_shutdown=5)
    return 0


def cmd_migrate(args) -> int:
    db = _db()
    print(f"schema at {db.revision()} in {_where(db)}")
    return 0


def cmd_demo(args) -> int:
    db = _db()
    with db.scope() as s:
        ws = s.scalar(select(Workspace).where(Workspace.slug == args.workspace))
        if ws is None:
            ws = Workspace(slug=args.workspace, name="Demo workspace")
            s.add(ws)
            s.flush()
        user = s.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            user = User(email=args.email.strip().lower(), name="Demo owner")
            s.add(user)
            s.flush()
        if s.get(Membership, (ws.id, user.id)) is None:
            s.add(Membership(workspace_id=ws.id, user_id=user.id, role="owner"))
        prog = s.scalar(select(Program).where(Program.workspace_id == ws.id, Program.slug == "quadruped"))
        if prog is None:
            from .contracts import CampaignSpec
            CampaignSpec(**{**DEMO_SPEC, "policy": "stand"})          # fails loudly if the demo drifts
            prog = Program(workspace_id=ws.id, slug="quadruped", name="Stand-in quadruped",
                           standard_spec={**DEMO_SPEC, "policy": None})
            s.add(prog)
            s.flush()
            for label, policy, note, base in DEMO_CHECKPOINTS:
                ck = Checkpoint(workspace_id=ws.id, program_id=prog.id, label=label, policy=policy, note=note)
                s.add(ck)
                s.flush()
                if base:
                    prog.baseline_checkpoint_id = ck.id
        state = Path(get_settings().state_dir)
        token_file = _token_file(s, ws, "runner", "demo runner", state / "runner-token")
        ci_file = _token_file(s, ws, "ci", "demo CI", state / "ci-token")
        s.commit()
        link = _link(s, ws, user)
    api = get_settings().public_url.rstrip("/")
    print(f"workspace  {args.workspace}  (owner {args.email}, an example address)")
    print(f"program    quadruped: {', '.join(c[0] for c in DEMO_CHECKPOINTS)} (baseline stand-v1)")
    print(f"\nsign in    {link}")
    print("           (one use, 30 minutes; 'teeter-api link' makes another)")
    print(f"\nrunner     teeter runner start --api {api} --token-file {_shown(token_file)} "
          f"--config runner/demo-runner.yaml")
    print(f"gate       teeter gate --api {api} --token-file {_shown(ci_file)} "
          f"--program quadruped --checkpoint tall-v2")
    return 0


def cmd_link(args) -> int:
    db = _db()
    with db.scope() as s:
        ws = _workspace(s, args.workspace)
        user = s.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None or s.get(Membership, (ws.id, user.id)) is None:
            sys.exit(f"{args.email} is not a member of {args.workspace}")
        print(_link(s, ws, user, args.minutes))
    return 0


def cmd_member(args) -> int:
    """Add someone to a workspace, or change their role. They sign in with
    the identity provider under this address, or with 'teeter-api link'."""
    db = _db()
    with db.scope() as s:
        ws = _workspace(s, args.workspace)
        email = args.email.strip().lower()
        user = s.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=args.name or "")
            s.add(user)
            s.flush()
        m = s.get(Membership, (ws.id, user.id))
        if m is None:
            s.add(Membership(workspace_id=ws.id, user_id=user.id, role=args.role))
        else:
            m.role = args.role
        s.commit()
    print(f"{email} is {'an' if args.role[0] in 'aeiou' else 'a'} {args.role} of {args.workspace}")
    return 0


def cmd_token(args) -> int:
    db = _db()
    with db.scope() as s:
        ws = _workspace(s, args.workspace)
        user = None
        if args.kind == "user":
            # a person's token acts as that person, with their role
            user = s.scalar(select(User).where(User.email == (args.email or "").strip().lower()))
            if user is None or s.get(Membership, (ws.id, user.id)) is None:
                sys.exit("error: a user token needs --email of a member of the workspace ('teeter-api member')")
        _, secret = mint(s, ws, args.kind, args.name, user=user)
        s.commit()
    print(secret)
    return 0


def _minutes(text: str) -> int:
    n = int(text)
    if not 1 <= n <= 7 * 24 * 60:
        raise argparse.ArgumentTypeError("between 1 minute and a week (10080)")
    return n


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="teeter-api", description="Run and administer a Teeter control plane.")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="migrate, then serve the API (and the app at /app/)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-migrate", action="store_true", help="start without migrating the database first")
    s.set_defaults(func=cmd_serve)
    sub.add_parser("migrate", help="bring the database to the latest schema").set_defaults(func=cmd_migrate)
    sub.add_parser("init", help="the same as migrate").set_defaults(func=cmd_migrate)
    d = sub.add_parser("demo", help="a demo workspace, program, runner token and sign-in link")
    d.add_argument("--workspace", default="demo")
    d.add_argument("--email", default="you@example.com")
    d.set_defaults(func=cmd_demo)
    lk = sub.add_parser("link", help="a one-time sign-in link")
    lk.add_argument("--workspace", default="demo")
    lk.add_argument("--email", default="you@example.com")
    lk.add_argument("--minutes", type=_minutes, default=30,
                    help="how long the link stays valid (default 30, at most a week)")
    lk.set_defaults(func=cmd_link)
    mb = sub.add_parser("member", help="add someone to a workspace, or change their role")
    mb.add_argument("--workspace", default="demo")
    mb.add_argument("--email", required=True)
    mb.add_argument("--role", choices=ROLES, default="engineer")
    mb.add_argument("--name", default="")
    mb.set_defaults(func=cmd_member)
    t = sub.add_parser("token", help="a new token, printed once")
    t.add_argument("--workspace", default="demo")
    t.add_argument("--kind", choices=("user", "ci", "runner"), default="ci")
    t.add_argument("--name", default="cli token")
    t.add_argument("--email", help="for --kind user: the member the token acts as")
    t.set_defaults(func=cmd_token)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
