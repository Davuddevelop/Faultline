# Teeter runner and CLI (`teeter-runner`)

The runner is the part that runs on the customer's machines. It dials out to
the control plane (`api/`), waits for a campaign it is allowed to run, runs it
on the engine (`harness/`), streams every evaluation back as it is measured,
reduces the failures, records each failure mode's minimal case, uploads that,
and reports the result. The customer opens no inbound port.

The same package carries `teeter`, the command line for people and CI.

## Start a runner

```sh
pip install -e harness -e runner          # the engine first; see api/README.md, "Package names"
teeter runner start --api https://… --token-file runner-token --config runner.yaml
```

The token is a runner token (`tt_run_…`) from the app's Runners page, or from
`teeter-api demo` locally. In Docker:

```sh
docker build -f runner/Dockerfile -t teeter-runner .
docker run --rm -e TEETER_API=https://… -e TEETER_TOKEN=tt_run_… teeter-runner
```

That image carries the demo allowlist. A customer's image starts `FROM` it and
adds its own robot files, policy checkpoints and `runner.yaml`.

## The allowlist

The control plane names robots and policies; it never sends a path or code.
The runner resolves each name against its own config and refuses any name that
is not listed, so a compromised server cannot make this machine read a file or
import a module its owner did not list (`teeter_runner/config.py`).

```yaml
name: lab-gpu-02                 # optional; --name overrides
max_workers: -1                  # cores for one campaign; -1 is all of them
robots:
  quadruped: ../harness/models/quadruped.xml     # relative to this file
policies:
  stand: stand                                   # the harness's built-in stance
  q2-v41: onnx:/srv/policies/q2-walk-v41.onnx    # illustrative name and path
```

`demo-runner.yaml` allows the stand-in quadruped and three policies: `stand`,
and `tall` and `crouch` from `teeter_runner/demo_policies.py`, which hold a
pose and are not trained policies.

## What leaves the machine

The robot files and the policy checkpoints do not. What the runner sends:

| When | What |
| --- | --- |
| Registering | its name, hostname, platform, core count, the MuJoCo, NumPy, Python, engine and runner versions, and the names in its allowlist |
| While a job runs | each evaluation: index, round, perturbation, severity, whether it failed or was invalid and why; a heartbeat with the phase and counts |
| Per failure mode | the minimal case's trace of the four signals (`trace.csv`) and, for the stand-in quadruped, a replay of its torso and feet (`replay.json`) |
| At the end | the result: failure modes, coverage, nominal values, counts, the robot file's SHA-256 and a summary of its joints and actuators, the policy's id, the environment's versions |

## Running a job

| Step | Where |
| --- | --- |
| Long-poll `/v1/runner/claim`; at most one job at a time | `agent.py` |
| A heartbeat thread renews the lease every third of it, and relays *canceled* and *lease lost* to the work, which stops at its next check, between evaluations | `agent.py`, `execute.Control` |
| The spec becomes the engine's own `Campaign`, through `faultline.config.parse`, so a campaign run here is the one `faultline run` would run from YAML | `execute.build` |
| Evaluations stream in batches: every 0.5 s or 50 samples, whichever comes first | `execute.Streamer` |
| Reduce, group into failure modes, re-run each minimal case for its trace and replay, upload, complete | `execute.execute` |
| Ctrl-C or SIGTERM hands the current job back as retryable and exits; a second Ctrl-C exits at once | `agent.py` |

The demo program's stand-v1 campaign, run this way through the API, finds 38
violations in 150 evaluations and a minimal push of 7.875 N·s (requested),
which is the published record's directed seed 0: same engine, same experiment,
same numbers.

## The CLI

Every command takes `--api` and `--token` or `--token-file`, or reads
`TEETER_API` and `TEETER_TOKEN`, which is how CI should pass them.

```sh
teeter campaign run spec.yaml        # plan a campaign (teeter.campaign/1) and follow it
teeter gate --program quadruped --checkpoint tall-v2
teeter status                        # the workspace at a glance
```

`teeter gate` runs the program's experiment on the checkpoint, and on the
baseline if it has not been run, then compares them. Exit code **0** passed,
**1** blocked (a failure mode is new or widened), **2** refused (the two runs
are not the same experiment) or error. A pass means the search found nothing
new or wider in its budget; it is not evidence that the checkpoint does not
fail.

## Tests

```sh
pip install -e harness -e api -e "runner[dev]"
cd runner && python -m pytest tests -q
```

`tests/test_end_to_end.py` starts a real API server on a random port and runs
the real agent against it on real physics: nothing is mocked.
