"""The Vercel build step for the control plane (pyproject.toml,
[tool.vercel.scripts]). Two jobs:

1. Copy the website and app (../teeter) into the package as teeter_api/site,
   since the function can only serve what is inside the project's root
   directory. The project setting "include files outside the root directory"
   makes ../teeter visible here.
2. On a production build, migrate the database before the new code serves a
   request. Preview builds never migrate: they would change the schema under
   production.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_SRC = HERE.parent / "teeter"
SITE_DST = HERE / "teeter_api" / "site"


def copy_site() -> None:
    if not (SITE_SRC / "app" / "index.html").exists():
        sys.exit(f"vercel_build: no site at {SITE_SRC}; enable 'Include files outside the root directory'")
    if SITE_DST.exists():
        shutil.rmtree(SITE_DST)
    shutil.copytree(SITE_SRC, SITE_DST, ignore=shutil.ignore_patterns("README.md", "*.py"))
    n = sum(1 for p in SITE_DST.rglob("*") if p.is_file())
    print(f"vercel_build: site copied, {n} files")


def migrate() -> None:
    env = os.environ.get("VERCEL_ENV", "")
    if env != "production":
        print(f"vercel_build: {env or 'local'} build, database left alone")
        return
    sys.path.insert(0, str(HERE))
    from teeter_api.db import Database
    from teeter_api.settings import get_settings
    s = get_settings()
    if not s.database_url.startswith("postgresql"):
        sys.exit("vercel_build: production needs DATABASE_URL (Postgres); refusing to deploy without one")
    db = Database(s.database_url, pool_size=1, direct_url=s.database_url_direct)
    print(f"vercel_build: schema at {db.migrate()}")
    db.engine.dispose()


if __name__ == "__main__":
    copy_site()
    migrate()
