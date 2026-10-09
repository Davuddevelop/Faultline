"""Configuration, from the environment only, so one image runs anywhere.

    TEETER_STATE_DIR      local state: the dev database, artifacts, demo tokens
                          (default .teeter/ in the checkout)
    TEETER_DATABASE_URL   postgresql+psycopg://user:pass@host/db, or sqlite:///path
                          (default a SQLite file in the state directory)
    TEETER_STORAGE_DIR    where artifacts are kept: replays, traces
                          (default storage/ in the state directory)
    TEETER_SITE_DIR       the website and app to serve at /, or empty for none
    TEETER_PUBLIC_URL     how browsers reach this server, for sign-in links
    TEETER_CORS_ORIGINS   comma-separated origins allowed to call the API
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _state() -> Path:
    return Path(os.environ.get("TEETER_STATE_DIR", str(REPO / ".teeter")))


def _default_site() -> str:
    site = REPO / "teeter"
    return str(site) if (site / "app" / "index.html").exists() else ""


@dataclass(frozen=True)
class Settings:
    state_dir: str = field(default_factory=lambda: str(_state()))
    database_url: str = field(default_factory=lambda: os.environ.get(
        "TEETER_DATABASE_URL", f"sqlite:///{_state() / 'dev.sqlite'}"))
    storage_dir: str = field(default_factory=lambda: os.environ.get(
        "TEETER_STORAGE_DIR", str(_state() / "storage")))
    site_dir: str = field(default_factory=lambda: os.environ.get("TEETER_SITE_DIR", _default_site()))
    public_url: str = field(default_factory=lambda: os.environ.get(
        "TEETER_PUBLIC_URL", "http://127.0.0.1:8000"))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in os.environ.get("TEETER_CORS_ORIGINS", "").split(",") if o.strip()))
    # how long a claimed job stays with a runner without a heartbeat
    lease_s: float = field(default_factory=lambda: float(os.environ.get("TEETER_LEASE_S", "60")))
    # the longest a runner's claim request waits for work before returning empty
    claim_wait_max_s: float = 25.0
    max_attempts: int = 3


def get_settings() -> Settings:
    return Settings()
