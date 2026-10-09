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
| Website (`teeter/`) | Live on Vercel; the older pages are retired from it (`docs/decisions.md` §4) |
| App (`teeter/app/`) | Live against the control plane when it serves the app; the labelled prototype everywhere else |
| Control plane (`api/`), runner and CLI (`runner/`) | **v0, built** (§3), and ready to host: migrations, private Blob storage, WorkOS sign-in, roles and a read-only demo are built; provisioning needs the account owner (`docs/decisions.md`) |

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
| API | FastAPI, SQLAlchemy 2, Alembic migrations | the same, on Vercel's Python runtime (`api/` as the project root) |
| Database | Postgres 16 (SQLite for tests and a no-install dev mode) | Neon Postgres, through the Vercel Marketplace |
| Queue | Postgres table, leases, `SKIP LOCKED`; long-poll, or `Retry-After` on Vercel | the same, plus `LISTEN/NOTIFY` where a long-lived server runs it |
| Storage | local directory, or a private Vercel Blob store | private Vercel Blob; an S3 backend if the API leaves Vercel |
| Live updates | polling with an index cursor | server-sent events |
| Sign-in | one-time links; WorkOS AuthKit built, on once its keys are set; roles enforced | WorkOS AuthKit, SAML and directory sync through it later |
| Runner | `teeter runner start`, from the checkout or `runner/Dockerfile` | the same, published as a pip package and an image |
| Web app | static files served by the API | the same, or Next.js once routing and auth outgrow it |

---

## 3. v0: the working demo (built)

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

All four were done on 9 October, natively against Postgres 16 and again in
Docker Compose. What was measured:

- The demo's stand-v1 campaign, through the API and the runner, found 38
  violations in 150 evaluations and a minimal push of 7.875 N·s (requested):
  the published record's directed seed 0, number for number.
- Gating tall-v2 against stand-v1 **blocked**, exit 1: the push mode widened,
  its minimal push 7.875 → 6.89 N·s (requested). The CI job `stack` asserts
  this on every push.
- Gating crouch-v3 **passed**, exit 0: its campaign found no violation in
  150 evaluations, so the baseline's mode is `not_found`, which is not
  evidence that crouch-v3 cannot fall.

**Built in v0**

- `api/`: workspaces, tokens, runners, programs, checkpoints, campaigns, the
  job queue with leases, evaluation ingest, failure modes, artifacts, gates,
  audit log. See `api/README.md`.
- `runner/`: register; long-poll for a job; renew its lease; run the engine
  with streaming; reduce; capture replays; upload; complete or fail. Plus the
  `teeter` CLI (`runner start`, `campaign run`, `gate`, `status`). See
  `runner/README.md`.
- The gate: two campaigns compare only if everything but the policy matches,
  robot file and MuJoCo version included. Otherwise the gate is refused, and
  the differing field is named.
- Live mode in `teeter/app/` (`js/live.js`) when the API serves it. The static
  site stays a labelled prototype, and screens not built yet keep the
  prototype's example data under a strip that says so.
- `make dev` (`scripts/dev.sh`), `docker compose up`, `api/Dockerfile`,
  `runner/Dockerfile`, and CI (`.github/workflows/ci.yml`): the three suites,
  the API's on Postgres too, the record check, and the stack with a gate.

**Added on 9 October, after v0** (the four decisions in `docs/decisions.md`):
Alembic migrations, run by `teeter-api migrate` and by the production build;
private Vercel Blob storage; the Vercel entrypoint, build step and
serverless claim (`Retry-After`), rehearsed locally with Vercel's settings;
roles enforced, with viewers read-only; a read-only demo workspace anyone can
open from the sign-in page; WorkOS AuthKit sign-in for invited addresses,
tested against a mocked WorkOS; and the older pages retired from the site.

**Not in v0:** the hosted deployment itself (built, not provisioned), SSO
connections, billing, signed manifests, hosted runners, Isaac Lab, more than
one region, emailed sign-in links, a members screen in the app.

---

## 4. From v0 to v1

| Milestone | Builds | Done when | Est. |
| --- | --- | --- | --- |
| **M1 · Deployable** | Built: migrations, Blob storage, the Vercel project's configuration, WorkOS sign-in, roles, the demo workspace. Left: provisioning (`docs/decisions.md`, an hour of the owner's clicks), structured logs and error tracking, the runner on PyPI and as a published image, server-sent events, a members screen | A design partner signs in at a real URL and connects a runner without our help | 1–2 wk left |
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
| Our package names are unclaimed | `faultline-harness`, `teeter-api` and `teeter-runner` are not on PyPI; anyone could publish them, and an install that misses the local copy would fetch theirs | Local packages install first everywhere (Makefile, CI, Dockerfiles); claim the names before M1 |

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
- The pages from the previous identity still quote the old numbers by hand.
  They are retired from the deployed site and redirected (`docs/decisions.md`
  §4), but still in the repository.

---

## 7. Decisions

Decided on 9 October; the reasons, costs and setup are in `docs/decisions.md`.

1. **Hosting:** Vercel for the control plane too, with Neon Postgres and a
   private Vercel Blob store. The Docker image stays for self-hosting.
2. **Sign-in:** WorkOS AuthKit, for invited addresses only.
3. **Simulator:** MuJoCo first. Isaac-trained policies are tested in MuJoCo
   through ONNX and a declared observation layout; an Isaac runner is M6.
4. **The older pages:** retired from the site and redirected; kept in the
   repository.
