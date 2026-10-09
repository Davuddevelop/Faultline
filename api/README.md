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
teeter-api demo                # a demo workspace, program, runner and CI tokens, a sign-in link
teeter-api serve               # http://127.0.0.1:8000
teeter-api link                # another sign-in link (one use, 30 minutes)
teeter-api token --kind ci     # a token for CI, printed once
```

`teeter-api demo` can be run again safely: it keeps the token files that this
database still honours and only mints what is missing.

## Configuration

The environment only, so one image runs anywhere (`teeter_api/settings.py`).

| Variable | Default | What |
| --- | --- | --- |
| `TEETER_STATE_DIR` | `.teeter/` in the checkout | dev database, artifacts, the demo's token files |
| `TEETER_DATABASE_URL` | SQLite in the state directory | `postgresql+psycopg://user:pass@host/db` in production |
| `TEETER_STORAGE_DIR` | `storage/` in the state directory | replays and traces |
| `TEETER_SITE_DIR` | `teeter/` in the checkout | the site and app served at `/`; empty for none |
| `TEETER_PUBLIC_URL` | `http://127.0.0.1:8000` | how browsers reach this server, for sign-in links |
| `TEETER_CORS_ORIGINS` | none | comma-separated origins allowed to call the API |
| `TEETER_LEASE_S` | `60` | how long a claimed job stays with a runner without a heartbeat |

## How it holds together

| Property | Where |
| --- | --- |
| **Stateless.** Everything is in the database and the artifact store, so replicas can be added behind a load balancer. | `app.py` |
| **The queue is a table.** A claim is a compare-and-swap on the job row; on Postgres the candidates are read `FOR UPDATE SKIP LOCKED`, so runners polling at once spread over different jobs. Tested with 8 runners and 24 jobs on SQLite and on Postgres: each job taken once. | `queue.py`, `tests/test_queue.py` |
| **Leases.** A runner renews its claim by heartbeat. A lapsed lease returns the job to the queue, up to 3 attempts, and a retry starts the campaign over rather than stitching two machines' results together. | `queue.py` |
| **Idempotent ingest.** Evaluations are keyed by `(campaign, index)` and inserted `ON CONFLICT DO NOTHING`; progress counters move only by what was actually new. | `queue.ingest` |
| **Long-poll claims.** `/v1/runner/claim` waits up to 25 s without holding a thread; shutdown gives open requests 5 s. | `routes/runner.py`, `cli.py` |
| **Tokens.** Three kinds (`tt_usr_`, `tt_ci_`, `tt_run_`), each scoped to one workspace and stored only as SHA-256. Sign-in links are one use and 30 minutes, and mint a user token that travels in the URL fragment, which browsers do not send to servers. | `security.py`, `routes/public.py` |
| **Multi-tenant.** Every row carries `workspace_id` and every query filters on it. | `models.py` |
| **Audit log.** Every write: who, what, when, from where. | `audit.py` |
| **Gates.** Two campaigns compare only if the robot file (by hash), MuJoCo version, space, rules, search, reduction, seeds, duration, control rate and observation layout all match: only the policy may differ. Otherwise the gate is refused and the differing field named. Each baseline mode is `widened`, `narrowed`, `unchanged` or `not_found` in the candidate, which can also have `new` ones; any new or widened mode blocks. `not_found` means the search did not find it, never that it is fixed. | `gate.py` |
| **Versioned contracts.** `teeter.campaign/1`, `teeter.evaluation/1`, `teeter.result/1`. The API restates the engine's axis table and signal list so it can run without MuJoCo; `tests/test_contracts.py` holds the two together. | `contracts.py` |

## Endpoints

| | |
| --- | --- |
| Public | `GET /v1/health`, `GET /v1/contracts`, `GET /v1/auth/link/{code}` |
| Workspace | `GET /v1/me`, `/v1/overview`, `/v1/runners`, `/v1/audit`; `GET POST /v1/tokens`, `DELETE /v1/tokens/{id}` |
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

- **Migrations.** Tables are created at start-up; Alembic comes before the
  first real data (M1).
- **Sign-in.** Links are printed by `teeter-api link`, not emailed; an
  identity provider replaces them (M1).
- **Storage.** Artifacts are kept on local disk; S3-compatible storage is M1.
- **Live updates.** The app polls with an index cursor; server-sent events are M1.
- **Roles.** A membership stores one (owner, admin, engineer, viewer), but nothing
  enforces it yet: every member can do everything.

## Package names

`teeter-api`, `teeter-runner` and `faultline-harness` are not registered on
PyPI by us or anyone else (checked 9 October 2026). Until they are claimed, a
`pip install` that does not find the local copy first would look for them on
the index, where anyone could publish under those names. The Makefile, CI and
Dockerfiles install the engine first for that reason.
