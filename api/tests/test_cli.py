"""teeter-api demo is run by scripts/dev.sh and by docker compose on every
start, so running it again must leave a working setup, not a stranded one."""

from __future__ import annotations

from sqlalchemy import func, select

from teeter_api import cli
from teeter_api.db import Database
from teeter_api.models import Checkpoint, Program, Token


def _demo(monkeypatch, tmp_path, capsys) -> str:
    monkeypatch.setenv("TEETER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("TEETER_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["demo"]) == 0
    return capsys.readouterr().out


def test_demo_writes_tokens_into_the_state_directory(monkeypatch, tmp_path, capsys):
    out = _demo(monkeypatch, tmp_path, capsys)
    state = tmp_path / "state"
    for name, prefix in (("runner-token", "tt_run_"), ("ci-token", "tt_ci_")):
        f = state / name
        assert f.read_text().startswith(prefix)
        assert f.stat().st_mode & 0o777 == 0o600
    assert "--token-file state/runner-token" in out
    assert "/v1/auth/link/" in out


def test_demo_again_keeps_valid_tokens_and_the_program(monkeypatch, tmp_path, capsys):
    _demo(monkeypatch, tmp_path, capsys)
    first = {n: (tmp_path / "state" / n).read_text() for n in ("runner-token", "ci-token")}
    _demo(monkeypatch, tmp_path, capsys)
    assert {n: (tmp_path / "state" / n).read_text() for n in first} == first
    db = Database(f"sqlite:///{tmp_path / 'state' / 'dev.sqlite'}")
    with db.scope() as s:
        assert s.scalar(select(func.count()).select_from(Token)) == 2
        assert s.scalar(select(func.count()).select_from(Program)) == 1
        assert s.scalar(select(func.count()).select_from(Checkpoint)) == 3
    db.engine.dispose()


def test_demo_replaces_a_token_this_database_does_not_know(monkeypatch, tmp_path, capsys):
    stale = tmp_path / "state" / "runner-token"
    stale.parent.mkdir(parents=True)
    stale.write_text("tt_run_from_some_other_database\n")
    _demo(monkeypatch, tmp_path, capsys)
    assert stale.read_text() != "tt_run_from_some_other_database\n"
    assert stale.read_text().startswith("tt_run_")
