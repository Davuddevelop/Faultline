# Teeter — engineering roadmap to v1

*Written 9 October 2026. Takes the product plan (`docs/product-plan.md`) from a
clickable prototype to software a design partner runs on its own machines.
**v0** is the working demo built now; **v1** is what the first design partner
uses in production. Durations are estimates for one person working with AI
help, not promises.*

---

## 1. Where things stand

| Piece | State |
| --- | --- |
| Engine (`harness/`, faultline 0.3.0) | Works: seven axes, four signals, random and CEM search, reduction, failure modes, reports, deterministic replay. Four bugs fixed on 9 October (§6). |
| Published campaign (`assets/data/campaign.json`) | Re-made by `tools/publish_campaign.py`; `--check` fails when the record and the engine disagree |
| Website (`teeter/`) | Live on Vercel |
| App (`teeter/app/`) | Clickable prototype on the published record and example data |
| Control plane, runner, live app | **v0, this milestone** (§3) |

---

## 2. Architecture

```
  customer network                                   Teeter cloud
 ┌──────────────────────────────┐               ┌──────────────────────────────┐
 │ teeter runner                │   HTTPS out   │ API (FastAPI), N replicas    │
 │  · harness + MuJoCo 3.12.0   │ ────────────▶ │  · stateless                 │
 │  · robots, policies:         │  claim, stream│ Postgres                     │
 │    allowlisted by name       │  results,     │  · source of truth           │
 │  · weights stay here         │  upload       │  · job queue (SKIP LOCKED)   │
 └──────────────────────────────┘  replays      │ object storage               │
                                                │  · replays, traces, archives │
  browser ──── HTTPS, token ──────────────────▶ │ web app (static files)       │
                                                └──────────────────────────────┘
```

### What makes it scale

1. **The API holds no state.** Everything lives in Postgres and object
   storage, so the API scales by adding replicas behind a load balancer.
2. **The queue is a table.** A runner claims a job with
   `SELECT … FOR UPDATE SKIP LOCKED`, so any number of runners can poll
   without two of them taking the same job. Each claim is a **lease**: the
   runner renews it while it works, and a lease that expires (the runner died
   or lost its network) returns the job to the queue. No message broker until
   Postgres cannot keep up. A claim happens once per campaign, not once per
   evaluation, so that point is far off.
3. **Determinism makes retries free.** A campaign re-run from its seeds
   produces the same samples in the same order. Results are keyed by
   `(campaign, index)` and ingested with `ON CONFLICT DO NOTHING`, so a runner
   that retries a request, or a job that is retried on another runner, cannot
   duplicate or corrupt anything.
4. **The runner dials out, and the server cannot reach in.** The customer
   opens no inbound port. The server names robots and policies, and the runner
   resolves those names against an allowlist in its own config. A compromised
   control plane cannot make a runner read an arbitrary file or import
   arbitrary code.
5. **Multi-tenant from the first row.** Every table carries `workspace_id`,
   every query filters on it, and every token is scoped to one workspace.
6. **Contracts are versioned.** The campaign spec, the run record, the runner
   protocol (`/v1/…`) and later the evidence pack each carry a version. Tests
   bind the API's spec schema to the engine's axis table and signal list, so
   they cannot drift apart silently.
7. **Big data stays out of the database.** Per-evaluation rows are small and
   live in Postgres. Replays, traces and archives go to object storage, which
   is local disk in development and S3 or R2 in production.
8. **Every write is in the audit log**: who, what, when, from where.

### Stack

| Layer | v0 (now) | v1 |
| --- | --- | --- |
| API | FastAPI, SQLAlchemy 2 | same, with Alembic migrations |
| Database | Postgres 16 (SQLite for tests and a no-install dev mode) | managed Postgres |
| Queue | Postgres table, leases, `SKIP LOCKED` | same, plus `LISTEN/NOTIFY` to wake waiting runners |
| Storage | local directory | S3-compatible (R2 or S3) |
| Live updates | polling with an index cursor | server-sent events |
| Sign-in | workspace tokens | an identity provider (WorkOS, per the plan), SAML later |
| Runner | `teeter runner start` | the same, as a pip package and a Docker image |
| Web app | static files served by the API | the same, or Next.js once routing and auth outgrow it |

---

## 3. v0: the working demo (now)

**Done when** a person can, on one laptop or across two machines:

1. Start the stack with one command. The API serves the app and prints a
   sign-in link.
2. Start a runner, which registers and appears on the Runners page.
3. Plan a campaign in the app. The runner claims it, evaluations stream into
   the live view, reduction runs, and the failure modes appear with a 3D replay
   of the real minimal case, recorded by the runner.
4. Run two checkpoints of one program, call `teeter gate`, and get **blocked**
   or **passed**, with exit code 1 when blocked. The two checkpoints are
   built-in demo poses, not trained policies, and the app says so.

**Built in v0**

- `api/`: workspaces, tokens, runners, programs, checkpoints, campaigns, the
  job queue, evaluation ingest, failure modes, artifacts, gates, audit log.
- `runner/`: register; long-poll for a job; renew its lease; run the engine
  with streaming; reduce; capture replays; upload; complete or fail. Plus the
  `teeter` CLI (`login`, `runner start`, `campaign run`, `gate`).
- The engine side of the gate: two campaigns compare only if robot, space,
  rules, search and seeds match. Otherwise the gate is refused, and the
  differing field is named.
- Live mode in `teeter/app/` when the API serves it. The static site stays a
  labelled prototype.
- `make dev`, Docker Compose, CI.

**Not in v0:** real accounts, SSO, billing, signed manifests, hosted
runners, Isaac Lab, more than one region.

---

## 4. From v0 to v1

| Milestone | Builds | Done when | Est. |
| --- | --- | --- | --- |
| **M1 · Deployable** | Hosted API, Postgres and object storage; sign-in through an identity provider; TLS and secrets; Alembic migrations; structured logs and error tracking; runner on PyPI and Docker Hub; server-sent events | A design partner signs in at a real URL and connects a runner without our help | 2–3 wk |
| **M2 · Onboarding** | The runner reports its allowlisted robots and policies with model cards and observation layouts; a smoke test as its own job type; ONNX and TorchScript checkpoints by file hash; URDF checklist; templates | A partner reaches a first finding on their own robot in a day | 3–4 wk |
| **M3 · Gate in CI** | GitHub Action, pull-request status and comment, Slack, baselines ("last shipped"), checkpoint history | One partner's CI calls `teeter gate` on every policy change | 2–3 wk |
| **M4 · Evidence** | Ed25519 runner keys sign manifests; evidence packs; assessor share links; archive download | An assessor re-runs one record from a pack | 4–6 wk |
| **M5 · Scale** | One campaign split across runners (CEM rounds as fan-out job batches); `LISTEN/NOTIFY`; evaluations partitioned by month; retention; quotas; metering into invoices | 10 runners on one campaign finish ~10× faster, with identical results | when needed |
| **M6 · Beyond MuJoCo** | Isaac Lab runner type; manipulation signals and axes; calibration against paired hardware runs | A campaign runs on an Isaac-trained policy in its own simulator | after a partner asks |

M1 to M4 together are **v1**. That is about 11 to 16 weeks after v0 (an
estimate).

---

## 5. Risks that decide the order

| Risk | Why it matters | What we do |
| --- | --- | --- |
| The partner trains in Isaac, not MuJoCo | Most locomotion policies are | M2 starts with their stack; M6 moves up if needed |
| Their security team refuses outbound traffic | Ends the hosted model | Fully self-hosted control plane, the same container (plan §2) |
| Requested is not delivered | Push and lag quantise on the control grid, so a requested 7.875 N·s push delivers 1.2× that at the default timing | M2 records delivered values beside requested ones |
| Long campaigns | Real policies run slower than the stand-in | Fan-out (M5); estimated wall time measured after the first evaluations |

---

## 6. Review of the Python, 9 October

Every Python file in the repository was read. Four bugs were found, fixed and
pinned by tests that fail on the old code:

| Bug | Effect | Fix |
| --- | --- | --- |
| `torque_loss_pct` scaled the servo gain but not its bias | Weaker motors moved their setpoints instead: at 15% the torso stood 17 mm taller | Bias scales with gain (`runner.py`) |
| `joint_pos` `relative` subtracted `qpos0` (zeros) | Isaac-style policies would get absolute angles | Subtract the keyframe pose (`model.default_joint_pos`) |
| Reduction skipped axes within tolerance of nominal, then called them required | A "required" axis could be one nobody tested | Probe elimination first (`reduce.py`) |
| `random_search` drew a whole point per axis | Six draws per point; the published record could not be reproduced | One draw per point (`search.py`) |

**Effect on what is published.** Re-made with `tools/publish_campaign.py` on
the fixed engine, the campaign has **one failure mode, not two**. The
push-plus-torque-loss mode was an artifact of the torque bug.

- **Directed search, seed 0:** 38 violations in 150 evaluations (was 51).
- **Uniform arm:** 12 of 750, a 95% Wilson interval of 0.9–2.8% (was 29 of
  750, 2.7–5.5%).
- **Headline, unchanged:** a requested 7.875 N·s push breaches
  `tilt_deg > 35.0` at 1.26 s.

The site, brand book, app, `/report/` and `/ink/` are rebuilt from the new
record.

**Known, and not yet fixed:**

- `seeds.sim` is recorded but nothing in the simulation draws on it.
- `friction_mu` is applied to every geom, not only the floor.
- The pages from the previous identity (`atlas/`, `surreal/`, `next/`,
  `start/`, `archive/`, `faultline.html`) still quote the old numbers by hand.

---

## 7. Decisions that are yours

1. **Hosting for M1.** Recommended: the API as a container on Fly.io or
   Railway, Postgres on Neon, storage on Cloudflare R2. Vercel keeps the
   website.
2. **Sign-in provider.** WorkOS, per the plan, or Clerk.
3. **Isaac Lab or MuJoCo first** for the first partner (plan §12).
4. **The old-identity pages:** retire them, or update their numbers.
