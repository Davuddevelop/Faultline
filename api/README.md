# Teeter control plane (`teeter-api`)

The API under `/v1`, and the website and app at `/`. It holds workspaces,
tokens, runners, programs and their checkpoints, campaigns, the job queue,
every evaluation a runner streams back, failure modes, artifacts, gates and the
audit log. It never imports the engine and never runs a simulation: runners do
that, on the customer's machines (`runner/`).

## Run it

```sh
make dev                       # or scripts/dev.sh: SQLite in .teeter/, the API and a runner
docker compose up --build -d   # Postgres, the API and a runner in containers
```

Both print a one-time sign-in link; open it, and the app at `/app/` runs
against this server. By hand:

```sh
pip install -e harness -e api -e runner   # the engine first; see "Package names" below
teeter-api demo                # migrate; a demo workspace, program, runner and CI tokens, a sign-in link
teeter-api serve               # migrate, then http://127.0.0.1:8000
teeter-api migrate             # bring the database to the latest schema
teeter-api link                # another sign-in link (one use, 30 minutes; --minutes for longer)
teeter-api member --email ada@example.com --role engineer   # invite someone
teeter-api token --kind ci     # a token for CI, printed once
```

`teeter-api demo` can be run again safely: it keeps the token files that this
database still honours and only mints what is missing. Every command reads the
database from the environment, so the same commands administer a laptop's
SQLite file and the hosted Postgres.

## Hosting

The hosted control plane is a Vercel project whose root directory is this
folder: `pyproject.toml` names the entrypoint (`teeter_api.asgi:app`) and a
build step, `vercel_build.py`, which copies `../teeter` in as the site and, on
production builds only, migrates the database. `vercel.json` sends `/` to the
app. Postgres comes from Neon and artifacts go to a private Blob store; the
reasons, the costs and the setup steps are in `docs/decisions.md`. The same
package runs anywhere else from `api/Dockerfile`.

## Configuration

The environment only, so one image runs anywhere (`teeter_api/settings.py`).

| Variable | Default | What |
| --- | --- | --- |
| `TEETER_STATE_DIR` | `.teeter/` in the checkout (`/tmp/teeter` on Vercel) | dev database, artifacts, the demo's token files |
| `TEETER_DATABASE_URL`, or `DATABASE_URL` | SQLite in the state directory | Postgres in production; `postgres://` URLs are read with psycopg 3 |
| `TEETER_DATABASE_URL_UNPOOLED`, or `DATABASE_URL_UNPOOLED` | the main URL | a direct connection for migrations, when the main one goes through a pooler |
| `TEETER_STORAGE` | `blob` if `BLOB_READ_WRITE_TOKEN` is set, else `local` | where replays and traces go |
| `BLOB_READ_WRITE_TOKEN` | none | a private Vercel Blob store's token |
| `TEETER_STORAGE_DIR` | `storage/` in the state directory | the directory for local storage |
| `TEETER_SITE_DIR` | `teeter/` in the checkout, or the copy in the package | the site and app served at `/`; empty for none |
| `TEETER_PUBLIC_URL` | the Vercel production URL, else `http://127.0.0.1:8000` | how browsers reach this server, for sign-in links |
| `TEETER_SECRET` | none | signs demo visits and sign-in state; at least 32 characters. Without it, neither exists |
| `TEETER_DEMO_WORKSPACE` | none | the slug of a workspace anyone may explore read-only from the sign-in page |
| `WORKOS_CLIENT_ID`, `WORKOS_API_KEY` | none | sign-in through WorkOS AuthKit; without them, sign-in is by link |
| `TEETER_CLAIM_WAIT_S` | `25` (`0` on Vercel) | how long a runner's claim may wait for work |
| `TEETER_CLAIM_RETRY_S` | `1` (`10` on Vercel) | after an empty claim, how long the runner is told to wait |
| `TEETER_DB_POOL_SIZE` | `10` (`2` on Vercel) | Postgres connections each process keeps |
| `TEETER_CORS_ORIGINS` | none | comma-separated origins allowed to call the API |
| `TEETER_LEASE_S` | `60` | how long a claimed job stays with a runner without a heartbeat |

## How it holds together

| Property | Where |
| --- | --- |
| **Stateless.** Everything is in the database and the artifact store, so replicas can be added behind a load balancer. | `app.py` |
| **The queue is a table.** A claim is a compare-and-swap on the job row; on Postgres the candidates are read `FOR UPDATE SKIP LOCKED`, so runners polling at once spread over different jobs. Tested with 8 runners and 24 jobs on SQLite and on Postgres: each job taken once. | `queue.py`, `tests/test_queue.py` |
| **Leases.** A runner renews its claim by heartbeat. A lapsed lease returns the job to the queue, up to 3 attempts, and a retry starts the campaign over rather than stitching two machines' results together. | `queue.py` |
| **Idempotent ingest.** Evaluations are keyed by `(campaign, index)` and inserted `ON CONFLICT DO NOTHING`; progress counters move only by what was actually new. | `queue.ingest` |
| **Claims.** `/v1/runner/claim` long-polls up to 25 s without holding a thread, or on Vercel returns at once; empty-handed it answers 204 with `Retry-After`, and the runner waits that long. Shutdown gives open requests 5 s. | `routes/runner.py`, `cli.py` |
| **Migrations.** Alembic owns the schema (`migrations/`). `migrate` holds a Postgres advisory lock, so two deployments cannot run it at once, and a test fails if the migrations and the models describe different schemas. | `db.py`, `tests/test_hosting.py` |
| **Tokens.** Three stored kinds (`tt_usr_`, `tt_ci_`, `tt_run_`), each scoped to one workspace, kept only as SHA-256, and able to expire. Sign-in links are one use, 30 minutes by default, and mint a user token that travels in the URL fragment, which browsers do not send to servers. | `security.py`, `routes/public.py` |
| **Roles.** A person's token carries their role in the workspace: owner, admin, engineer or viewer. Viewers read everything and are refused every change; the audit log, which records addresses, is for those who may change things; owners and admins manage members. | `security.py`, `routes/auth_workos.py` |
| **Demo visits.** With `TEETER_DEMO_WORKSPACE` and `TEETER_SECRET` set, anyone may explore that workspace read-only for twelve hours. The pass (`tt_demo_`) is signed, not stored, so visits add no rows. | `security.py`, `routes/public.py` |
| **WorkOS sign-in.** AuthKit proves who someone is; only an address a workspace invited is let in, with its role. The OAuth state is signed and bound to a cookie. Browser sessions last 30 days. | `routes/auth_workos.py` |
| **Artifacts.** A local directory, or a private Vercel Blob store spoken to over its HTTP API. The API is the only reader. | `storage.py` |
| **Multi-tenant.** Every row carries `workspace_id` and every query filters on it. | `models.py` |
| **Audit log.** Every write: who, what, when, from where. | `audit.py` |
| **Gates.** Two campaigns compare only if the robot file (by hash), MuJoCo version, space, rules, search, reduction, seeds, duration, control rate and observation layout all match: only the policy may differ. Otherwise the gate is refused and the differing field named. Each baseline mode is `widened`, `narrowed`, `unchanged` or `not_found` in the candidate, which can also have `new` ones; any new or widened mode blocks. `not_found` means the search did not find it, never that it is fixed. | `gate.py` |
| **Versioned contracts.** `teeter.campaign/1`, `teeter.evaluation/1`, `teeter.result/1`. The API restates the engine's axis table and signal list so it can run without MuJoCo; `tests/test_contracts.py` holds the two together. | `contracts.py` |

## Endpoints

| | |
| --- | --- |
| Public | `GET /v1/health`, `GET /v1/contracts`, `GET /v1/auth/methods`, `GET /v1/auth/link/{code}`, `POST /v1/auth/demo`, `GET /v1/auth/workos/login`, `GET /v1/auth/workos/callback` |
| Workspace | `GET /v1/me`, `/v1/overview`, `/v1/runners`, `/v1/audit`; `GET POST /v1/tokens`, `DELETE /v1/tokens/{id}`; `GET POST /v1/members`, `DELETE /v1/members/{email}` |
| Campaigns | `GET POST /v1/campaigns`; `GET /v1/campaigns/{ref}`, `…/evaluations?after=`, `…/artifacts/{name}`; `POST …/cancel` |
| Programs and gates | `GET POST /v1/programs`; `GET /v1/programs/{slug}`; `POST …/checkpoints`; `PUT …/baseline`; `POST …/gate` (what CI calls); `GET POST /v1/gates`; `GET /v1/gates/{ref}` |
| Runner protocol | `POST /v1/runner/register`, `/claim`; `POST /v1/runner/jobs/{id}/heartbeat`, `/evaluations`, `/complete`, `/fail`; `PUT /v1/runner/jobs/{id}/artifacts/{name}` |

The OpenAPI schema is at `/v1/openapi.json` and browsable at `/v1/docs`.

## Tests

```sh
cd api && python -m pytest tests -q
TEETER_TEST_DATABASE_URL=postgresql+psycopg://teeter@127.0.0.1:5432/teeter_test \
  python -m pytest tests -q          # every database test on Postgres too
```

## Not built yet

Each is in `docs/v1-roadmap.md`, with the milestone that brings it.

- **The hosted deployment itself.** Built and rehearsed; it needs the account
  owner to create the project and connect its storage (`docs/decisions.md`).
- **Live updates.** The app polls with an index cursor; server-sent events are M1.
- **Logs and error tracking.** Plain logs to stdout; structured logs and Sentry
  are M1.
- **A members screen.** Members are managed through the API and
  `teeter-api member`; the app's settings screen for it is still the prototype.

## Package names

`teeter-api`, `teeter-runner` and `faultline-harness` are not registered on
PyPI by us or anyone else (checked 9 October 2026). Until they are claimed, a
`pip install` that does not find the local copy first would look for them on
the index, where anyone could publish under those names. The Makefile, CI and
Dockerfiles install the engine first for that reason.
