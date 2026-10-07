# Teeter — product plan

*Written 7 October 2026. Turns the harness into a product a robotics company
signs a contract for. It decides the architecture, every screen, how a company
gets from sign-in to a first finding, and what makes the product hard to copy.
Everything marked **built** exists in this repo today; everything else is
**to build**.*

---

## 0. The decisions, in one screen

| Question | Decision |
| --- | --- |
| What is the product? | A **regression gate for learned robot policies**: every new checkpoint is searched for the conditions that break it, compared with the last one, and blocked if it got worse. Evidence for certifiers falls out of the same records. |
| Where does it run? | **Split.** A web app (the control plane, run by us) holds workspaces, results and reports. A **runner** (installed by the customer, on their machines) holds the robot, the policy and the simulator. Weights never leave the customer. |
| How does a company start? | Invite-only. Sign in, create a workspace, install the runner with one command, connect a robot and a policy, run a smoke test, then a first campaign. Target: first finding in under a day, with us on a call. |
| What does an engineer do daily? | Push a checkpoint. CI runs a campaign through the runner. Teeter posts a verdict (pass or blocked) with what got worse, new, or fixed. The engineer opens the failure mode and replays it. |
| What is hard to copy? | Not the UI and not CEM. The calibration data (paired sim/real results), the evidence format certifiers learn to read, the adapter library, and the gate wired into each customer's CI. Section 8. |
| What is the base we expand on? | Four versioned contracts: the **campaign spec**, the **run record**, the **runner protocol**, the **evidence pack**. New simulators, robots, axes and rules plug into those without changing the product around them. Section 9. |

---

## 1. What exists, and what does not

The harness (`harness/faultline/`, about 2,900 lines, tested) is the engine.
The product is everything around it.

| Capability | Status | Where |
| --- | --- | --- |
| Load MJCF, warn on URDF | built | `model.py` |
| Declared observation layout (Isaac Lab / legged_gym names) | built | `observe.py` |
| ONNX and TorchScript policies | built | `adapters.py` |
| Seven perturbation axes, four signals, explicit predicates | built | `space.py`, `predicates.py`, `runner.py` |
| Random and CEM search, parallel workers | built | `search.py` |
| Reduction to a minimal case, failure modes, coverage | built | `reduce.py`, `report.py` |
| Engineering report, safety appendix, archive | built | `report.py` |
| Deterministic replay checked against a trajectory hash | built | `record.py` |
| CLI: `init`, `run`, `replay`, `version` | built | `cli.py` |
| Compare two checkpoints (new, widened, fixed, unchanged) | **to build** | engine |
| Runner that takes jobs from a server | **to build** | new package |
| Web app, accounts, workspaces | **to build** | new |
| CI integration (GitHub Actions, GitLab) | **to build** | new |
| Signed manifests | **to build** | engine + runner |
| Calibration (simulation results corrected by paired hardware runs) | **to build** | engine, roadmap phase B |
| Isaac Lab / Isaac Sim backend | **to build** | engine |

---

## 2. Architecture

```
  customer network                                   Teeter cloud
 ┌─────────────────────────────────┐               ┌──────────────────────────┐
 │  teeter runner                  │  outbound     │  control plane           │
 │   · robot model (MJCF)          │  HTTPS only   │   · web app              │
 │   · policy weights   ← stay     │ ────────────▶ │   · API                  │
 │   · simulator (MuJoCo 3.12.0)   │  results,     │   · Postgres             │
 │   · campaign engine             │  hashes,      │   · object storage       │
 │   · signing key                 │  failure      │     (archives, traces)   │
 │                                 │  traces       │   · auth, billing        │
 │  their CI  ──▶ teeter CLI ──────┼──────────────▶│                          │
 └─────────────────────────────────┘               └──────────────────────────┘
```

**Why split.** A robotics company's trained policy is its most valuable asset;
security review ends the conversation if we ask for it. A pure on-premise tool
cannot show trends, compare checkpoints across a team, or hand an auditor a
link. The split is the pattern of GitHub Actions self-hosted runners and
Buildkite agents: the runner dials out, so the customer opens no inbound port.

**What leaves the customer.** Campaign specs; per-evaluation axis values,
severities and verdicts; failure-mode summaries; signal traces for failure
modes only (on by default, can be switched off); file hashes of the model,
policy and config; the recorded environment. **Never** the policy weights, and
the robot model only if the customer uploads it to the web app themselves.

**Three ways to deploy**, in order of when we offer them:

1. **Cloud + self-hosted runner.** The default for everyone.
2. **Fully self-hosted.** The control plane as a container image inside their
   network, for customers whose security team allows no outbound traffic. Offered
   once a customer requires it, not before.
3. **Hosted runners.** We run the simulation on our compute, for teams with no
   spare machines who accept uploading the policy. Later, and opt-in.

**Stack, chosen for one founder.** Web app: Next.js on Vercel (the site already
deploys there). API: Python (FastAPI), so the engine and the API share code and
types. Database: managed Postgres. Archives: S3-compatible storage. Jobs: a
Postgres-backed queue the runner long-polls; no message broker until it hurts.
Auth: WorkOS (email, Google, GitHub; SAML SSO when a customer asks). Billing:
Stripe invoices on annual contracts; no self-serve checkout at first.

---

## 3. The objects

These are the nouns the whole product uses. They match the harness vocabulary.

| Object | What it is | Example |
| --- | --- | --- |
| **Workspace** | A customer company. Billing, members, SSO. | `acme-robotics` |
| **Program** | One robot product line. The unit of the licence. | `Quadruped Q2` |
| **Robot** | A versioned robot model file, identified by its SHA-256. | `q2.xml · 4f1c…` |
| **Policy** | A trained controller family, with its observation layout. | `q2-walk` |
| **Checkpoint** | One version of a policy, identified by its file hash. | `q2-walk v41` |
| **Space** | The declared perturbation volume: axes and ranges, in real units. | `push 0–9 N·s, slope 0–10°…` |
| **Rule set** | The predicates that define failure. | `tilt_deg > 35.0` (grace 0.3 s) |
| **Campaign** | One search of a space against a checkpoint under a rule set. | `C-0001` |
| **Evaluation** | One simulation inside a campaign. | 150 per campaign |
| **Failure mode** | Failures grouped by what they need, with a minimal case. | `tilt_limit via push_impulse_ns` |
| **Gate** | The comparison of a checkpoint's campaign with its baseline. | `v41 vs v40: blocked` |
| **Evidence pack** | Signed, re-runnable records for one release. | `EP-2027-01` |
| **Runner** | A machine running `teeter runner`, with its own signing key. | `lab-gpu-02` |

A campaign is only comparable with another if their **robot hash, space and
rule set match**. The product refuses comparisons across a changed space and
says which field differs. A comparison across a changed space looks meaningful
and is not.

---

## 4. The journeys

### 4.1 First day: sign-in to first finding

Target: under a day, with a Teeter engineer on a call for the first customers.

1. **Invite.** Early on, accounts are invite-only. Every workspace is set up
   with us; that is the pilot.
2. **Sign in** with Google, GitHub or an email link. Enterprise SSO later.
3. **Create the workspace** and the first program.
4. **Install the runner**: `pip install teeter`, `teeter login`, `teeter runner
   start`. The web app shows the runner appear, with its Python, MuJoCo and CPU
   details.
5. **Connect the robot.** Upload or point at an MJCF. The web app shows what was
   read: joints, actuators, bodies, the floating base. A URDF gets a warning
   that contact parameters and actuator dynamics must be checked; a CAD file is
   refused with the reason.
6. **Connect the policy.** ONNX or TorchScript file on the runner, or a Python
   `module:Class`. Map the **observation layout** term by term (joint
   positions, base angular velocity, projected gravity…) and the action scale.
   The page prints the layout so the engineer can diff it against training code.
7. **Smoke test.** One nominal run with no perturbation. The robot must stand
   (or walk) and the rules must not fire. If it falls with nothing pushing it,
   the mapping is wrong, and the page says so before a campaign wastes an
   afternoon. This one check prevents most bad first impressions.
8. **First campaign** from a template ("legged robot, push and slope"). Results
   stream in live. The first failure mode appears with a replay.

### 4.2 Every day: the gate

1. An engineer trains `v41` and pushes it.
2. Their CI calls `teeter gate --program q2 --checkpoint v41.onnx`.
3. The runner runs the program's standard campaign (same space, same rules, same
   seeds as the baseline).
4. Teeter compares with the baseline checkpoint and posts a verdict to the pull
   request and to Slack: **blocked, 2 new modes, 1 widened**, or **passed**.
5. The engineer opens the gate page, then the widened mode, sees the policy now
   falls at a requested 6.2 N·s where it used to hold to 7.9, and replays it.
6. When a checkpoint ships, it becomes the new baseline.

### 4.3 Release: evidence

1. The safety lead opens **Evidence**, picks a release checkpoint, and builds a
   pack: method, space, coverage, rules, every failure mode, the run manifest.
2. The pack is signed by the runner keys that produced it.
3. An external assessor gets a **read-only link**. They see the pack, can
   download the archive, and can re-run any record with `teeter replay`; the
   page shows whether the environment matches.
4. Nothing in the pack calls the policy safe. It says what was searched, what
   was found, and what was not covered.

### 4.4 Admin

Invite members, set roles, connect SSO, add CI and Slack, issue runner tokens
and API keys, see the audit log, see the plan and its programs.

---

## 5. What companies will face, and what the product does about it

| Friction | Why it happens | What the product does |
| --- | --- | --- |
| **Their robot is URDF, or in Isaac** | Most teams train in Isaac Lab with USD or URDF; MuJoCo wants MJCF with contact and actuator parameters | Phase A: guided URDF → MJCF conversion with a checklist (friction, damping, gear). Later: an Isaac Lab backend behind the same runner protocol |
| **Observation mismatch** | A policy expects a precise vector in a precise order; a wrong layout gives confident wrong actions | The layout editor plus the smoke test. Wrong mappings fail loudly before any campaign |
| **Control rate and action scaling** | Training at 50 Hz with scaled actions; running at another rate silently changes the policy | Control rate and action scale are fields on the policy, recorded with every run |
| **"Your simulator is wrong"** | Sim-to-real gap; the first objection every engineer raises | Phase B calibration: paired hardware runs correct simulation estimates. Until then, every finding is labelled as found in simulation, with a replay they can check themselves |
| **Compute** | Large campaigns need cores | The runner uses every core it is given; campaigns state their estimated wall time before they start |
| **Security review** | Uploading weights is a red line | Weights never leave. The runner dials out only. A data sheet lists exactly what is sent |
| **IP and legal** | Contracts, data rights, export rules | Standard pilot agreement with the data-rights clause; data processing terms; EU entity before selling evidence in the EU |
| **Trust in an unknown tool** | Nobody bets a release on a stranger's software | Pilots run with us in the room; every result re-runs from its seeds on their own machine |
| **Adoption by the team** | A tool nobody opens dies | The gate lives where they already work: the pull request and Slack |

---

## 6. Every screen

Routes are for the web app at `app.teeter.dev` (illustrative: the domain is
not registered). **R** marks where the data comes from: *record* means the real
campaign record in this repo; *example* means illustrative data in the
prototype, labelled as such on screen.

### Public and account

| Route | Screen | What it holds |
| --- | --- | --- |
| `/login` | **Sign in** | Google, GitHub, email link; "SSO" field for enterprise domains; invite-only notice |
| `/invite/:token` | **Accept invite** | Workspace name, inviter, role, sign-in buttons |
| `/onboarding` | **Set up** | Six steps with a progress rail: workspace → program → runner → robot → policy → smoke test. Each step checks itself and says what failed |

### Workspace

| Route | Screen | What it holds | R |
| --- | --- | --- | --- |
| `/` | **Overview** | Each program's latest gate (pass/blocked), open regressions, campaigns running now, runner health, robustness trend per program | example + record |
| `/programs/:p` | **Program** | Robot, policy, baseline checkpoint, standard campaign spec, checkpoint timeline with the minimal failing push per checkpoint | example |
| `/programs/:p/checkpoints` | **Checkpoints** | Every checkpoint with hash, gate verdict, modes, date, who pushed | example |
| `/robots/:r` | **Robot** | Model card: format, hash, joints, actuators, bodies, floating base, warnings; observation layout of the policies that use it | record (model) |
| `/policies/:id` | **Policy** | Format, hash, observation layout table, action scale, control rate, smoke-test result | record (layout) |
| `/campaigns` | **Campaigns** | Table: id, program, checkpoint, method, budget, violations, modes, duration, verdict; filters | record + example |
| `/campaigns/new` | **New campaign** | Space (seven axes, real units), rules (sentence preview), search (method, budget, seeds), runner, estimated wall time; valid on load | record (defaults) |
| `/campaigns/:id/live` | **Live run** | Progress, evaluations streaming onto the scatter, first violation marker, runner log | record (replayed) |
| `/campaigns/:id` | **Campaign result** | Verdict; failure modes first; coverage; efficiency; reduction; environment; actions | record |
| `/campaigns/:id/modes/:m` | **Failure mode** | Minimal case per axis; when the rule fired; trace with threshold; 3D replay; axes eliminated; locally-minimal note; re-run command | record |
| `/gates/:id` | **Compare checkpoints** | Two checkpoints; **widened**, **new**, **fixed**, **unchanged**; blocked/passed; refuses mismatched specs | example (shape) |
| `/evidence` | **Evidence** | Packs per release; contents; signatures; replay status; share with an assessor | record (archive) |
| `/evidence/:id/share` | **Assessor view** | Read-only pack for an external reader; replay instructions; environment match | record |
| `/library` | **Spaces and rules** | Reusable spaces and rule sets, versioned; which programs use them | record |
| `/runners` | **Runners** | Each runner: status, host, cores, versions, jobs, key fingerprint; install command | example |
| `/integrations` | **Integrations** | GitHub Actions, GitLab CI, Slack; API keys; webhook log | example |
| `/settings/*` | **Settings** | Workspace, members and roles, SSO, plan and programs, audit log, data handling | example |

### Roles

| Role | Can |
| --- | --- |
| Owner | Everything, including billing and deleting the workspace |
| Admin | Members, SSO, integrations, runners |
| Engineer | Programs, campaigns, gates, evidence drafts |
| Viewer | Read everything inside the workspace |
| Assessor (external) | Read one shared evidence pack; nothing else |

Every write is in the audit log: who, what, when, from where.

---

## 7. Sign-in and accounts

- **Invite-only during pilots.** The sign-in page says so plainly and offers a
  way to ask for access.
- **Methods:** Google, GitHub, email magic link. **SAML SSO** (Okta, Azure AD)
  when a customer requires it; enforced per email domain.
- **Runner tokens** are created per runner and scoped to one workspace; each
  runner also generates its own signing key on first start and registers only
  the public half.
- **API keys** for CI are scoped per program and can be revoked; last-used time
  is shown.
- **Sessions:** short-lived, with re-authentication before deleting data or
  changing SSO.

---

## 8. What a vibe coder can copy, and what they cannot

**Copyable in weeks.** The interface. A CEM loop. A CLI that runs MuJoCo with
pushes. A dashboard. The seven axes. Anyone with a weekend and an AI assistant
can build a convincing demo of those, so the business cannot rest on them.

**Not copyable, and how the product builds each from the first customer:**

1. **Calibration data.** Paired simulation and hardware results per robot and
   policy family. The design-partner contract asks for them; the product stores
   them with each campaign. A copy starts with none.
2. **An evidence format assessors know.** The pack is designed with the first
   notified bodies, versioned, and re-runnable. Once an assessor has read ten of
   ours, a new format has to win that trust from zero.
3. **The adapter library.** Every customer adds robot formats, observation
   conventions, policy formats and simulator quirks that ship to the next
   customer. Integration time falls with each one; a copy pays it every time.
4. **The gate in their CI.** Once every checkpoint passes through Teeter and the
   history of modes lives there, switching means losing the history and
   re-wiring CI. That is where retention comes from.
5. **Failure-mode priors.** Across customers (anonymised, with consent), where
   policies of a robot class tend to break, used to start the search in the
   right place. Searches get cheaper with every customer.
6. **Reproducibility guarantees.** Pinned simulators, three seeds, signed
   manifests and checked replays are tedious to get right, and are exactly what
   a hostile reader tests first.

---

## 9. The base we expand on

Four contracts are versioned from day one. Everything new plugs into one of them.

| Contract | Version | What it fixes | How it extends |
| --- | --- | --- | --- |
| **Campaign spec** (`campaign.yaml`) | v1 | Robot, policy, space, rules, search, seeds | New axes and signals add fields; old specs stay valid |
| **Run record** | v1 | One evaluation: inputs, environment, hashes, verdict | New simulators record their own environment fields |
| **Runner protocol** | v1 | How a runner claims a job, streams results, signs them | New backends (Isaac Lab) are new runner types |
| **Evidence pack** | v1 | What a pack contains and how it is signed | New sections per regulation or standard |

Extension points, in the order they will probably be needed: an **Isaac Lab
backend**; **manipulation** (arms: grasp-force and drop signals, object-mass and
pose axes); **terrain** axes; **rule types** beyond threshold predicates
(sequences, durations); **calibration** (phase B); **drones** later.

---

## 10. Building it

Estimates are estimates for one person working with AI help; they are not
promises.

| Phase | Builds | Done when |
| --- | --- | --- |
| **0 · Prototype** (now) | Every screen as a clickable prototype on real campaign data (`teeter/app/`) | A robotics engineer can click through a realistic first day and daily gate |
| **1 · Runner and gate** (~6–8 weeks) | Checkpoint comparison in the engine; `teeter gate`; the runner protocol; minimal API and database; sign-in; campaign, result, mode and gate pages for real | One design partner's CI calls `teeter gate` on a real checkpoint |
| **2 · Onboarding** (~4–6 weeks) | URDF conversion checklist; observation-layout editor; smoke test; runner management; GitHub and Slack | A second partner gets to a first finding in a day |
| **3 · Evidence** (~6 weeks) | Signed manifests; evidence packs; assessor share link | An assessor reads a pack and re-runs one record |
| **4 · Calibration** (roadmap phase B) | Paired hardware runs; corrected estimates with intervals | A campaign states a calibrated interval, shown correct on synthetic ground truth |

---

## 11. Plans inside the product

| Plan | Who | What is switched on |
| --- | --- | --- |
| **Pilot** | One program, 6–10 weeks | Everything, with us on calls; data-rights clause |
| **Production** | Per program, annual | Gate in CI, unlimited campaigns on their runners, Slack, history |
| **Evidence** | Per release | Signed packs, assessor links |
| **Enterprise** | Large customers | SSO, fully self-hosted control plane, audit export |

Prices are in `docs/strategy.md` and are estimates.

---

## 12. Open questions

1. Will the first customers accept outbound traffic from a runner, or demand
   fully self-hosted from the start?
2. MuJoCo first, or Isaac Lab first? Most locomotion training happens in Isaac;
   the harness is MuJoCo. The first partner's stack decides.
3. Who signs contracts: an entity in Azerbaijan, or an EU entity from the start?
4. Is the gate's baseline the last shipped checkpoint, or the previous one? Let
   each program choose; default to last shipped.
