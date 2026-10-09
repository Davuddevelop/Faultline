"""Configuration, from the environment only, so one image runs anywhere.

    TEETER_STATE_DIR        local state: the dev database, artifacts, demo tokens
                            (default .teeter/ in the checkout)
    TEETER_DATABASE_URL     postgresql://user:pass@host/db, or sqlite:///path. When it is
                            not set, DATABASE_URL is read, the name Neon and Vercel give it
                            (default a SQLite file in the state directory)
    TEETER_DATABASE_URL_UNPOOLED   a direct connection for migrations, when the main URL
                            goes through a connection pooler (or DATABASE_URL_UNPOOLED)
    TEETER_STORAGE          where artifacts are kept: "local", a directory, or "blob", a
                            private Vercel Blob store reached with BLOB_READ_WRITE_TOKEN
                            (default blob when that token is set, local otherwise)
    TEETER_STORAGE_DIR      the directory for local storage (default storage/ in the state
                            directory)
    TEETER_SITE_DIR         the website and app to serve at /, or empty for none
    TEETER_PUBLIC_URL       how browsers reach this server, for sign-in links
    TEETER_CORS_ORIGINS     comma-separated origins allowed to call the API
    TEETER_LEASE_S          how long a claimed job stays with a runner without a heartbeat
    TEETER_CLAIM_WAIT_S     how long a runner's claim may wait for work before returning
    TEETER_CLAIM_RETRY_S    after an empty claim, how long the runner should wait to ask again
    TEETER_DB_POOL_SIZE     connections each process keeps open to Postgres
    TEETER_DEMO_WORKSPACE   the slug of a workspace anyone may look around, read-only, from
                            the sign-in page; unset, there is no such workspace
    TEETER_SECRET           signs demo visits and sign-in state; at least 32 random characters.
                            Without it there are no demo visits and no identity provider
    WORKOS_CLIENT_ID, WORKOS_API_KEY   sign-in through WorkOS AuthKit (auth_workos.py);
                            unset, sign-in is by link only

On Vercel (VERCEL is set) three defaults change to suit a serverless function:
a claim returns at once instead of long-polling, which would keep an instance
alive and billed while it waits; runners are told to ask again in ten seconds;
and each instance keeps a small pool, since there can be many instances.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parent.parent


def _env(*names: str, default: str = "") -> str:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def _on_vercel() -> bool:
    return bool(os.environ.get("VERCEL"))


def _state() -> Path:
    return Path(os.environ.get("TEETER_STATE_DIR", str(REPO / ".teeter")))


def normalise_db_url(url: str) -> str:
    """psycopg 3 is the driver. Neon and most providers hand out postgres://
    or postgresql:// URLs, which SQLAlchemy would read as psycopg2."""
    for scheme in ("postgres://", "postgresql://"):
        if url.startswith(scheme):
            return "postgresql+psycopg://" + url[len(scheme):]
    return url


def _database_url() -> str:
    return normalise_db_url(_env("TEETER_DATABASE_URL", "DATABASE_URL",
                                 default=f"sqlite:///{_state() / 'dev.sqlite'}"))


def _database_url_direct() -> str:
    direct = _env("TEETER_DATABASE_URL_UNPOOLED", "DATABASE_URL_UNPOOLED")
    return normalise_db_url(direct) if direct else _database_url()


def _default_site() -> str:
    """The checkout's teeter/ folder, or the copy the Vercel build puts in the
    package (vercel_build.py)."""
    for site in (REPO / "teeter", PACKAGE / "site"):
        if (site / "app" / "index.html").exists():
            return str(site)
    return ""


def _public_url() -> str:
    explicit = os.environ.get("TEETER_PUBLIC_URL")
    if explicit:
        return explicit
    if os.environ.get("VERCEL_ENV") == "production" and os.environ.get("VERCEL_PROJECT_PRODUCTION_URL"):
        return "https://" + os.environ["VERCEL_PROJECT_PRODUCTION_URL"]
    host = _env("VERCEL_BRANCH_URL", "VERCEL_URL")
    return f"https://{host}" if host else "http://127.0.0.1:8000"


@dataclass(frozen=True)
class Settings:
    state_dir: str = field(default_factory=lambda: str(_state()))
    database_url: str = field(default_factory=_database_url)
    database_url_direct: str = field(default_factory=_database_url_direct)
    storage: str = field(default_factory=lambda: os.environ.get(
        "TEETER_STORAGE", "blob" if _env("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN") else "local"))
    storage_dir: str = field(default_factory=lambda: os.environ.get(
        "TEETER_STORAGE_DIR", str(_state() / "storage")))
    blob_token: str = field(default_factory=lambda: _env("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN"))
    site_dir: str = field(default_factory=lambda: os.environ.get("TEETER_SITE_DIR", _default_site()))
    public_url: str = field(default_factory=_public_url)
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in os.environ.get("TEETER_CORS_ORIGINS", "").split(",") if o.strip()))
    # how long a claimed job stays with a runner without a heartbeat
    lease_s: float = field(default_factory=lambda: float(os.environ.get("TEETER_LEASE_S", "60")))
    # the longest a runner's claim request waits for work before returning empty,
    # and how long the runner is told to wait before asking again
    claim_wait_max_s: float = field(default_factory=lambda: float(
        os.environ.get("TEETER_CLAIM_WAIT_S", "0" if _on_vercel() else "25")))
    claim_retry_s: float = field(default_factory=lambda: float(
        os.environ.get("TEETER_CLAIM_RETRY_S", "10" if _on_vercel() else "1")))
    db_pool_size: int = field(default_factory=lambda: int(
        os.environ.get("TEETER_DB_POOL_SIZE", "2" if _on_vercel() else "10")))
    max_attempts: int = 3
    demo_workspace: str = field(default_factory=lambda: os.environ.get("TEETER_DEMO_WORKSPACE", ""))
    secret: str = field(default_factory=lambda: os.environ.get("TEETER_SECRET", ""))
    workos_client_id: str = field(default_factory=lambda: _env("TEETER_WORKOS_CLIENT_ID", "WORKOS_CLIENT_ID"))
    workos_api_key: str = field(default_factory=lambda: _env("TEETER_WORKOS_API_KEY", "WORKOS_API_KEY"))

    @property
    def demo_enabled(self) -> bool:
        return bool(self.demo_workspace and len(self.secret) >= 32)

    @property
    def workos_enabled(self) -> bool:
        return bool(self.workos_client_id and self.workos_api_key and len(self.secret) >= 32)


def get_settings() -> Settings:
    return Settings()
