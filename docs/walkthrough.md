# Walkthrough: the whole product, step by step

Every step below was run on 14 October 2026 from a fresh clone of the branch
`claude/faultline-landing-spec-179f9n`, on Linux x86-64 with 4 cores, Python
3.11.15, MuJoCo 3.12.0 and NumPy 2.4.6. The outputs quoted are what it printed;
the timings are that machine's. On another operating system or CPU the numbers
can differ slightly: the engine reproduces bit for bit within one simulator
build and CPU architecture, and records its environment so that a difference
can be told apart from a defect.

What is real and what is a stand-in:

- The robot is a stand-in quadruped (`harness/models/quadruped.xml`). The demo
  checkpoints `stand-v1`, `tall-v2` and `crouch-v3` hold a pose; they are not
  trained policies. The ONNX policies in step 10 are small random networks, not
  trained ones.
- Everything happens in simulation. Nothing here has run on hardware.
- `you@example.com` and `ada@example.com` are example addresses. This build
  sends no email.
- The engine finds failures; it cannot show their absence. A gate that passes
  means the search found nothing new or wider within its budget, and no more.

## The cast

A real deployment has four parties. Locally you play all of them.

| Who | Does | With |
| --- | --- | --- |
| Operator | runs the control plane; mints tokens and sign-in links | `teeter-api`, `make dev` or Docker |
| Robotics engineer | owns the robot model and the policy files, runs a runner on their own machine, reads the results | `teeter runner start`, `runner.yaml`, the app |
| CI | adds each exported checkpoint and gates it | `teeter checkpoint add`, `teeter gate` |
| Reviewer | reads the evidence, changes nothing | the app, as a viewer |

## 1. Get the code

`main` holds only the website until pull request #13 is merged. The engine's
command line, the control plane and the runner are on the branch:

```sh
git clone -b claude/faultline-landing-spec-179f9n https://github.com/Davuddevelop/Faultline.git
cd Faultline
```

You need Python 3.10 or newer, `git` and `make`. Docker is optional (step 13).

## 2. Install, and check the checkout works

```sh
make install     # .venv/ with the engine, the control plane and the runner
make test        # all three suites
make check       # re-runs the published campaign and compares it with the record
source .venv/bin/activate     # faultline, teeter and teeter-api on your PATH, in every terminal you open
```

| Command | Took | Ends with |
| --- | --- | --- |
| `make install` | 42 s cold, 23 s with pip's cache warm | no output on success |
| `make test` | 75 to 86 s | `193 passed, 4 skipped`, `63 passed`, `8 passed` |
| `make check` | 35 to 38 s | `record matches the engine` |

The four skipped tests need the ONNX runtime, which step 10 installs.

## 3. The engine alone

This is what a customer gets from installing the engine: no server, no
account, nothing leaves the machine. (Its package name, `faultline-harness`, is
not on PyPI yet, so it comes from the checkout.) Work in a folder beside the
checkout, so nothing you make lands in the repository:

```sh
mkdir ../try && cd ../try
faultline version
faultline init                 # writes campaign.yaml, every line commented
faultline run campaign.yaml    # 20 s here
```

```
cem      seed=41279  failures  37/120  first at   60  best severity  +145.0    6.8s

1 failure mode(s) from the 10 most severe of 37:
  1. 10 x  tilt_limit via push_impulse_ns

coverage  68/1024 cells (6.64%) at 4 bins per axis
```

The exit code is 1 because violations were found; 0 would mean none were
found, which bounds nothing. In `deliverables/`:

| File | For |
| --- | --- |
| `engineering-report.md` | the team that trained the policy: each failure mode and its minimal case, here `push_impulse_ns 7.875 N.s requested`, first firing at t = 1.26 s |
| `safety-appendix.md` | someone assessing the evidence who built none of it: method, rules, declared space, coverage, environment, limits |
| `archive/manifest.jsonl` | every simulation: its seeds, configuration hash, model hash, policy id, perturbation and verdict |
| `archive/campaign.json`, `archive/report.json` | the campaign and the report as data |
| `archive/traces/mode-1.csv` | the minimal case's four signals over time |

How to read it:

- 37 of 120 is a count from a **directed** search (CEM), which spends its
  budget where failures are dense. It is not a failure rate; only a uniform
  search (`method: random`) supports one (step 8).
- **Requested**: the push is applied on the 50 Hz control grid, so the robot
  received a quantised amount, not exactly 7.875 N·s. Sensor lag is the same.
- The minimal case is **locally minimal**: no single axis can be relaxed
  further within its tolerance. A different combination could still be smaller.
- 6.64% coverage says where the search looked, and nothing about the rest.

Run it again and the archive is identical:

```sh
sha256sum deliverables/archive/manifest.jsonl
faultline run campaign.yaml -q
sha256sum deliverables/archive/manifest.jsonl     # the same digest
```

A single run can be recorded and re-executed by someone else, which is what
"evidence someone hostile can re-run" means at the smallest scale:

```sh
python ../Faultline/harness/examples/run_one.py        # one run, recorded to harness/runs/<id>.json
faultline replay ../Faultline/harness/runs/<id>.json   # matched, with both trajectory digests
```

`faultline run` itself does not write per-run records; for a campaign, re-run
it and compare `manifest.jsonl` as above.

## 4. The whole product on this machine

Back in the repository root, in a terminal you leave open:

```sh
make dev
```

```
workspace  demo  (owner you@example.com, an example address)
program    quadruped: stand-v1, tall-v2, crouch-v3 (baseline stand-v1)

sign in    http://127.0.0.1:8000/v1/auth/link/…
           (one use, 30 minutes; 'teeter-api link' makes another)
…
· the app is at http://127.0.0.1:8000/app/ — open the sign-in link above
…
registered as 'vm-dev' with http://127.0.0.1:8000: robots quadruped; policies crouch, stand, tall
```

That is the control plane (the API, the site and the app on port 8000, with
SQLite in `.teeter/`) and one runner using `runner/demo-runner.yaml`, named
after the host (`vm-dev` here). `.teeter/` also holds a runner token and a CI
token. It is git-ignored; keep it that way.

## 5. The engineer, in the app

Open the sign-in link.

1. **Overview**: one runner online, no campaigns yet.
2. **Programs → Stand-in quadruped.** A program fixes one experiment, its
   standard spec (robot, axes, rules, search, seeds); each checkpoint supplies
   only a policy.
3. **Run** on `stand-v1`, the baseline. The live page fills as the runner
   measures: 150 evaluations in about 9 s here.
4. **Open result**: `1 failure mode found. Smallest: push_impulse_ns 7.875 N·s
   requested, breaching at 1.26 s. Found in simulation, MuJoCo 3.12.0; nothing
   here was run on hardware.`
5. **The failure mode**: the minimal case, the axes relaxed away (every one
   but the push), the four signals over time and a 3D replay of the torso and
   feet.

The live page's count (38 of 150 violated) again describes the directed
search, not the robot. The run is recorded against `stand-v1`, so the gates in
step 6 reuse it instead of running the baseline again.

## 6. CI, from a second terminal

In the repository root, with the venv active:

```sh
export TEETER_API=http://127.0.0.1:8000 TEETER_TOKEN=$(cat .teeter/ci-token)
teeter gate --program quadruped --checkpoint tall-v2
teeter gate --program quadruped --checkpoint crouch-v3
teeter status
```

```
G-0001: tall-v2 (C-0002) against the baseline stand-v1 (C-0001)

BLOCKED: the candidate fails in a way the baseline did not, or under a smaller condition
  widened    tilt_limit via push_impulse_ns   push_impulse_ns 7.875 -> 6.89323 N.s requested
```

That took 10 s and exited 1.

```
G-0002: crouch-v3 (C-0003) against the baseline stand-v1 (C-0001)

PASSED: no failure mode is new or widened against the baseline
  not_found  tilt_limit via push_impulse_ns
```

That took 4 s and exited 0. Then:

```
Demo workspace (demo) at http://127.0.0.1:8000
  runners   1 of 1 online
  campaigns 3 done
  gates     1 blocked, 1 passed
```

The exit code is the contract with CI: **0** passed, **1** blocked (a failure
mode is new, or fails under a smaller condition than the baseline's), **2**
refused (the two runs are not the same experiment) or an error. `not_found`
means this search did not find that mode for `crouch-v3`; it is not evidence
the mode is gone. In a pipeline the gate is one step after export; an
illustrative GitHub Actions step, with secret names of your choosing:

```yaml
- run: teeter gate --program quadruped --checkpoint "$CHECKPOINT"
  env:
    TEETER_API: ${{ secrets.TEETER_API }}
    TEETER_TOKEN: ${{ secrets.TEETER_CI_TOKEN }}
```

## 7. A second runner

Runners run on the customer's machines and dial out; nothing dials in to them.
Here the second machine is a folder beside the checkout, `../laptop-2`, so its
token and files stay out of the repository. In a third terminal, from the
repository root:

```sh
mkdir -p ../laptop-2 && cp harness/models/quadruped.xml ../laptop-2/
cd ../laptop-2
```

In the app: **Runners → Add a runner**, name it `laptop-2`, **Make the
token**. The token is shown once, with the commands for the machine. It goes
in a file, not on a command line, where shell history and `ps` would keep it:

```sh
cat > runner-token && chmod 600 runner-token     # paste the token, then Enter and Ctrl-D
```

Then:

```sh
cat > runner.yaml <<'EOF'
name: laptop-2
max_workers: 2                    # cores for one campaign; -1 is all of them
robots:
  quadruped: quadruped.xml        # relative to this file
policies:
  stand: stand
EOF
teeter runner start --api http://127.0.0.1:8000 --token-file runner-token --config runner.yaml   # leave it running
```

```
registered as 'laptop-2' with http://127.0.0.1:8000: robots quadruped; policies stand
```

`runner.yaml` is the allowlist: the only robots and policies this machine will
run. The control plane only ever sends names, and a runner refuses any name
its own file does not list, so a compromised server cannot make it open a file
or import a module its owner did not list. The robot file and the policy files
never leave the machine; `runner/README.md` lists what does. Across real
machines the runner needs to reach the control plane: the hosted one, or
`teeter-api serve --host 0.0.0.0` on a network you trust.

## 8. Plan a campaign in the app, then from a terminal

**New campaign** builds a spec from what the online runners allow. In the
rehearsal: policy `stand`, only `push_impulse_ns` and `slope_deg`, **Uniform ·
random**, budget 80, **Start campaign**. It finished in about 7 s:

```
12 of 80 uniform samples violated a rule: a 95% Wilson interval of 8.8–24.4%, over the declared box only.
Smallest: push_impulse_ns 7.6077 N·s requested, breaching at 1.58 s.
```

This one is a rate, because the samples were uniform, and it is a rate over
the box that was declared (requested pushes from 0 to 9 N·s, slopes from 0 to
10°), not over the world. **Copy** the spec panel into `../try/uniform.yaml`, and the
same campaign runs from a terminal (the CI token from step 6 will do):

```sh
teeter campaign run ../try/uniform.yaml
```

```
C-0005 queued: quadruped / stand
…
    5 x  tilt_limit via push_impulse_ns   minimal: push_impulse_ns 7.60774 N.s requested   first breach 1.58 s
```

It exits 1 when violations were found. A campaign runs on whichever allowed
runner claims it first, and the numbers do not depend on which: in an earlier
pass the same uniform campaign, with `tall`, ran once on each runner and gave
identical results. The smallest requested push here, 7.6077 N·s, is not step 5's 7.875:
reduction shrinks a case from wherever the search found it, and two searches
can end at different local minima. Both are real; neither is the threshold.
Add `workers: -1` under `search:` to use every core the runner allows.

## 9. A reviewer who changes nothing

**Settings → Members → Invite** `ada@example.com` as a **viewer**. Until WorkOS
is configured no email goes out, so the operator makes a one-time link, from
the repository root:

```sh
teeter-api link --workspace demo --email ada@example.com
```

Opened in another browser, the link signs her in as a viewer. She sees every
campaign, failure mode, replay and gate; the Run and Gate buttons are gone,
New campaign explains why, and the API refuses her as well:

```
403 {"error":{"code":"read_only","message":"a viewer can look but not change anything in this workspace"}}
```

**Settings → Audit log**, as the owner, shows who did what: the invite, the
runner token, every campaign created, claimed and completed, every gate.

## 10. Your own policy

This is the step a customer's engineer cares about. Export the policy to ONNX
(`torch.onnx.export`) or TorchScript (`torch.jit.save`) with dropout and
sampling off: the engine refuses a file that answers the same observation twice
with different actions. To try the path without a checkpoint,
`harness/examples/stand_in_onnx.py` writes a small random network of the right
shape; it is not a trained policy. In a fourth terminal, in `../laptop-2` with
the venv active (the third is running the runner):

```sh
pip install -e "../Faultline/harness[onnx]" onnx     # the runtime, and onnx for the stand-in script
python ../Faultline/harness/examples/stand_in_onnx.py my-policy.onnx 0
```

The engine has to build the observation the policy was trained on, term by
term and in order. The terms are `joint_pos`, `joint_vel`, `base_quat`,
`base_lin_vel`, `base_ang_vel`, `projected_gravity`, `prev_action`, `qpos`,
`qvel` and `constant`, each with an optional `scale`, and `relative` for the
joint positions. A campaign for the engine alone, `campaign.yaml`:

```yaml
robot: quadruped.xml
policy: onnx:my-policy.onnx     # relative to this file, as the robot is
base_body: torso
observation:                    # the order and scaling the policy was trained on
  - {term: projected_gravity}
  - {term: base_ang_vel}
  - {term: joint_pos, relative: true}
  - {term: joint_vel, scale: 0.05}
duration_s: 5.0
seeds: {sampler: 0, sim: 0, policy: 0}
axes:
  push_impulse_ns: [0, 9]
  slope_deg: [0, 10]
predicates:
  - {name: tilt_limit, signal: tilt_deg, op: ">", threshold: 35.0, grace_s: 0.3}
  - {name: fallen, signal: height_m, op: "<", threshold: 0.12, grace_s: 0.3}
search: {method: cem, budget: 120}
reduce: {enabled: true, max: 10, budget: 200}
report: {out: deliverables}
```

`faultline run campaign.yaml` took 28 s: 70 of 120 directed evaluations
violated a rule, one failure mode, minimal push 7.826 N·s requested. The
archive names the policy `my-policy@ebfbca3d1b9b`: the file's name and the
first twelve hex digits of its SHA-256, so an overwritten file cannot pass for
the one that was tested. The stand-in script is deterministic, so yours should
carry the same id.

Through the product, list the file in the allowlist and restart the runner
(Ctrl-C, then the same `teeter runner start`), because a runner reports its
allowlist when it starts:

```yaml
policies:
  stand: stand
  my-policy: onnx:my-policy.onnx    # your exported checkpoint
```

The spec for the control plane, `spec.yaml`, is the same campaign except that
`robot` and `policy` are names from the allowlist and `report` is left out:

```yaml
robot: quadruped
policy: my-policy
base_body: torso
observation:
  - {term: projected_gravity}
  - {term: base_ang_vel}
  - {term: joint_pos, relative: true}
  - {term: joint_vel, scale: 0.05}
duration_s: 5
seeds: {sampler: 0, sim: 0, policy: 0}
axes:
  push_impulse_ns: [0, 9]
  slope_deg: [0, 10]
predicates:
  - {name: tilt_limit, signal: tilt_deg, op: ">", threshold: 35, grace_s: 0.3}
  - {name: fallen, signal: height_m, op: "<", threshold: 0.12, grace_s: 0.3}
search: {method: cem, budget: 120, workers: -1}
reduce: {enabled: true, max: 10, budget: 200}
```

```sh
export TEETER_API=http://127.0.0.1:8000 TEETER_TOKEN=$(cat ../Faultline/.teeter/ci-token)
teeter campaign run spec.yaml
```

It ran on `laptop-2`, the only runner that allows that policy, in 25 s: 70 of
120 again, minimal push 7.82554 N·s requested, the engine's own numbers.

## 11. Your own program and checkpoints, as CI would

The loop a team runs on every export: make the program once; then, for each
new checkpoint, allow it on a runner, add it and gate it. A program is made
with a member's token, which the operator mints, from the repository root:

```sh
teeter-api token --workspace demo --kind user --email you@example.com --name "laptop CLI" > ../laptop-2/user-token
```

Then, in `../laptop-2`, the program from the spec above, and its first
checkpoint, with the CI token still in the environment:

```sh
teeter program create --token-file user-token --slug my-robot --name "My robot" spec.yaml
teeter checkpoint add --program my-robot --label v1 --policy my-policy
```

```
program my-robot: robot quadruped, 2 axis(es), cem, 120 evaluations
  the spec's policy (my-policy) is left out: each checkpoint names its own
my-robot/v1: policy my-policy, the baseline
```

The next export: make it, list it in `runner.yaml` (`my-policy-v2:
onnx:my-policy-v2.onnx`), restart the runner, add it and gate it:

```sh
python ../Faultline/harness/examples/stand_in_onnx.py my-policy-v2.onnx 1
teeter checkpoint add --program my-robot --label v2 --policy my-policy-v2 --note "second export"
teeter gate --program my-robot --checkpoint v2
```

```
my-robot/v2: policy my-policy-v2
G-0003: v2 (C-0008) against the baseline v1 (C-0007)

PASSED: no failure mode is new or widened against the baseline
  unchanged  tilt_limit via push_impulse_ns   push_impulse_ns 7.82554 -> 7.64648 N.s requested
```

The gate took 49 s, because `v1` had never run this program's experiment and
ran first; a second gate reused that run and took 24 s. `v2`'s minimal
requested push moved by 0.18 N·s, inside the 0.5 N·s to which reduction
resolves that axis, so it reads as unchanged. A command-line token wins over
`TEETER_TOKEN`, so `--token-file user-token` acts as you even with CI's token
exported.

## 12. A stranger looking around

With `TEETER_SECRET` (at least 32 random characters) and
`TEETER_DEMO_WORKSPACE=demo` set where the API runs, the sign-in page offers
**Explore Demo workspace**: read-only, for twelve hours, without an account.

```sh
TEETER_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))") TEETER_DEMO_WORKSPACE=demo make dev
```

The visitor appears as "Demo visitor · read-only". The hosted sign-in page is
meant to offer the same (`docs/decisions.md`, step 4 of the hosted setup).

## 13. The same in Docker, on Postgres

```sh
TEETER_PORT=8300 make up      # 58 to 73 s here, base images already pulled; prints the sign-in link
docker compose run --rm runner gate --api http://api:8000 --token-file /data/ci-token \
  --program quadruped --checkpoint tall-v2
make down                     # the volumes, and so the data, stay
```

Inside the stack the gate blocked `tall-v2` with the same widened push,
7.875 → 6.89323 N·s requested, on Postgres instead of SQLite.

## What a company would have that this does not yet

| | Today | Where |
| --- | --- | --- |
| A hosted control plane | built and rehearsed, not provisioned; eight steps only the account owner can do | `docs/decisions.md`, "The setup only the account owner can do" |
| Email invitations and single sign-on | the operator sends one-time links; WorkOS AuthKit is wired in but not configured | `docs/decisions.md`, decision 2 |
| Packages on PyPI | install from a checkout; `faultline-harness`, `teeter-api` and `teeter-runner` are not registered | `docs/decisions.md` |
| Checkpoints known by file hash | names in `runner.yaml`, reported when the runner starts | M2 in `docs/v1-roadmap.md` |
| A real robot and a trained policy | the stand-in quadruped, held poses and random networks | the first design partner |
| Hardware | none; every number here comes from simulation | |
