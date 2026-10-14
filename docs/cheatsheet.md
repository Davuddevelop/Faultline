# Cheat sheet: what goes in, what comes out, what to do

**What you want:** the physical conditions under which your policy breaks a
rule you wrote, the smallest such condition as evidence someone else can
re-run, and a CI step that blocks a checkpoint that breaks in a new way or
under a smaller condition. It finds failures; it cannot show there are none.
Everything runs in simulation. Every step, with what it prints, is in
`docs/walkthrough.md`.

## What goes in

| Input | Format | Must have |
| --- | --- | --- |
| Robot | MJCF, `.xml` | hinge or slide joints and an `<actuator>` section; a `<keyframe>` for the standing pose. A URDF (`.urdf`) has no actuators or contact settings: convert it to MJCF and add them. CAD files (STEP, SolidWorks) cannot be used. |
| Policy | ONNX `.onnx`, TorchScript `.pt` `.pth` `.ts`, or Python as `module:Attr` | one observation in, one value per actuator out, the same answer every time (dropout and sampling off), no recurrent state. `stand` is the built-in baseline. |
| Observation | `observation:` list in the YAML | the terms in the order and scaling the policy was trained on: `joint_pos`, `joint_vel`, `base_quat`, `base_lin_vel`, `base_ang_vel`, `projected_gravity`, `prev_action`, `qpos`, `qvel`, `constant` |
| Base | `base_body:` in the YAML | the body that is pushed and whose tilt and height the rules read; defaults to the first free-floating body |
| Conditions | `axes:` in the YAML | a range for any of `push_impulse_ns`, `slope_deg`, `sensor_lag_ms`, `torque_loss_pct`, `payload_kg`, `payload_offset_m`, `friction_mu` |
| Rules | `predicates:` in the YAML | a threshold on `tilt_deg`, `height_m`, `contact_force_n` or `joint_vel_rads`, with a grace time |
| Search | `search:` and `seeds:` in the YAML | `cem` finds failures fast but gives no rate; `random` samples evenly and gives a rate; a budget; three seeds |

The files they live in:

| File | Format | Read by |
| --- | --- | --- |
| `campaign.yaml` | YAML, with file paths | `faultline run`, the engine alone |
| `runner.yaml` | YAML: names → files on this machine | `teeter runner start`; it runs nothing it does not list |
| `spec.yaml` | YAML or JSON (`teeter.campaign/1`), with names, not paths | `teeter campaign run`, `teeter program create` |
| `runner-token`, `ci-token`, `user-token` | one line of text | `--token-file`; never commit them |

## What comes out

From `faultline run`, in `deliverables/`:

| File | Format | What |
| --- | --- | --- |
| `engineering-report.md` | Markdown | each failure mode and its smallest case, for the people who trained the policy |
| `safety-appendix.md` | Markdown | method, rules, space, coverage, environment, limits, for someone checking the evidence |
| `archive/manifest.jsonl` | JSON Lines | one line per simulation: seeds, hashes, policy id, conditions, verdict |
| `archive/campaign.json`, `archive/report.json` | JSON | the campaign and the report as data |
| `archive/traces/mode-N.csv` | CSV | the smallest case's four signals over time |

Through the product (a runner and the control plane): the campaign, its
failure modes and every gate in the app, and as JSON from
`GET /v1/campaigns/{ref}` and `GET /v1/gates/{ref}`; per failure mode,
`modes/{i}/trace.csv` (CSV) and, for a robot built like the stand-in
quadruped, `modes/{i}/replay.json` (the 3D replay).

| Exit code | 0 | 1 | 2 |
| --- | --- | --- | --- |
| `faultline run` | nothing found, which bounds nothing | violations found | bad config |
| `teeter campaign run` | nothing found | violations found | campaign failed or canceled, or an error |
| `teeter gate` | passed | blocked | refused (not the same experiment), or an error |

## What to do

```sh
# once
git clone -b claude/faultline-landing-spec-179f9n https://github.com/Davuddevelop/Faultline.git
cd Faultline && make install && source .venv/bin/activate

# your policy, on the engine alone, in a folder outside the checkout
faultline init                  # then set robot, policy, observation, axes and rules in campaign.yaml
faultline run campaign.yaml     # read deliverables/engineering-report.md

# the product on this machine
make dev                        # open the sign-in link it prints
teeter runner start --api http://127.0.0.1:8000 --token-file runner-token --config runner.yaml

# every new checkpoint, in CI, with TEETER_API and TEETER_TOKEN (the CI token) set
teeter checkpoint add --program my-robot --label v42 --policy my-policy-v42
teeter gate --program my-robot --checkpoint v42      # exit 1 blocks the merge
```

`my-robot`, `v42` and `my-policy-v42` are illustrative names: yours come from
`teeter program create` and your `runner.yaml`.

## How to read a result

- A count from `cem` describes the search, not the robot. Only `random` gives
  a failure rate, and only over the ranges you declared.
- `push_impulse_ns` and `sensor_lag_ms` are requested values: they land on the
  control grid (50 Hz unless `control_hz` says otherwise), so the robot
  received a rounded amount.
- The smallest case is locally minimal: a different combination could be
  smaller still.
- A gate that passes found nothing new or wider within its budget. It does not
  show the checkpoint is safe.
