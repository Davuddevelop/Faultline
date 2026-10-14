# Prompt: get a trained policy ready for Teeter

Paste the block below into the Claude Code chat of the project where the policy
was trained. It asks that Claude to prepare a `teeter-handoff/` folder and to
check it, without touching the training. Every requirement in it is read from
`harness/faultline/` (`model.py`, `observe.py`, `adapters.py`, `runner.py`,
`config.py`); update it when they change.

```text
I want to test the robot policy trained in this project with Teeter, an adversarial testing harness for learned robot control policies (its engine is called Faultline). In MuJoCo, it searches a declared space of physical conditions (pushes, slopes, sensor lag, weaker motors, payload, friction) for the ones that make a frozen policy break a rule I write, and shrinks each failure to its smallest case. It finds failures; it cannot show there are none, and everything it does is in simulation.

Your job: read this project, prepare a folder teeter-handoff/ with the files below, and run the checks below. Do not change the training code, do not retrain, and do not tune anything to make results look better. Where you cannot establish something from the code or from a measurement, write UNKNOWN in teeter-handoff/HANDOFF.md and say what would settle it; never guess silently. Never describe the policy as safe, verified, validated or certified.

FIRST, FIND OUT (write each in HANDOFF.md with the file and line it comes from)
1. The simulator and version used for training, its physics timestep, and the policy's control rate (steps per second, i.e. 1 / (timestep x decimation)).
2. The robot description used (URDF, MJCF or USD), its joints, and the joint order in the policy's action vector and in its observation.
3. How actions become motor commands: action scale, the default (standing) joint pose added to it, clipping, PD gains (stiffness, damping), torque limits.
4. The exact observation vector: every component in order, its size, units, frame (world or body), scale, clipping and normalisation (for example a running mean/std), plus any history stacking, velocity commands, gait-phase clocks, height scans or other sensors.
5. The checkpoint: file, architecture, whether it is recurrent, and how the deterministic action is taken (the mean, not a sample).

WHAT TEETER NEEDS

A. The robot, as MJCF: robot.xml, with any meshes beside it, loadable by MuJoCo 3.12.0 (mujoco.MjModel.from_xml_path).
- The robot's joints as hinge or slide joints; the base as a free-floating body (a freejoint).
- An <actuator> section with one actuator per controlled joint. Every control step Teeter writes the policy's output vector straight into data.ctrl, so output i drives actuator i, in the order the actuators appear in the file. Match the training actuator model: for PD position control use <position> actuators with kp equal to the training stiffness and kv (or joint damping) equal to the training damping, and forcerange with forcelimited="true" equal to the torque limits.
- A <keyframe> (the first one is used) with the standing pose in qpos and the matching joint targets in ctrl. Every run starts from it, and relative joint positions are measured from it.
- <option timestep> equal to the training physics timestep, so that (1 / control rate) / timestep equals the training decimation.
- A ground plane, ideally a geom named floor: its friction is the nominal value for the friction axis.
If the robot is a URDF, convert it (MuJoCo loads URDF, and mujoco.mj_saveLastXML writes MJCF), then add the actuators, the keyframe and the floor. A URDF on its own has no actuators and is refused.

B. The policy, as one of:
- ONNX (policy.onnx): exactly one input, the observation, float32 of shape [batch, N] or [N]; the first output is the action.
- TorchScript (policy.pt, made with torch.jit.script or torch.jit.trace and saved with torch.jit.save; a state_dict will not load): it is called with one float32 tensor of shape [1, N] and must return one tensor, not a tuple.
- A Python class, referenced as module:Attr, with reset(seed) and act(obs, t) returning one float per actuator and an id attribute naming its version. Use this only for what a file cannot carry: a stateful observation history, a phase clock computed from t, a recurrent state.
It must be deterministic: the same observation gives the same action every time. Teeter checks an ONNX file with a fixed input width and refuses one that is not; nothing checks a TorchScript or Python policy, so check it yourself. A file policy must not be recurrent. Its output must already be the actuator commands, so bake into the exported graph everything training did after the network: action scale, default-pose offset, clipping, and any reordering from the policy's joint order to the MJCF actuator order. Bake observation normalisation and reordering into the input side the same way. Export once and do not overwrite the file afterwards: Teeter names a policy file by its content hash.

C. The observation, as a list. Teeter assembles it every control step in the order listed, multiplying each term by its scale, and does nothing else: no clipping, no normalisation, no history.
- joint_pos: positions of the hinge and slide joints, in MJCF joint order; with relative: true, minus the keyframe pose.
- joint_vel: their velocities.
- base_quat: the base orientation, w x y z, in the world frame.
- base_lin_vel: the base linear velocity in the base's own (body) frame.
- base_ang_vel: the base angular velocity in the body frame.
- projected_gravity: the unit vector (0, 0, -1) in the body frame.
- prev_action: the policy's previous output exactly as returned, after whatever scaling you baked in. If training fed back the raw network output, undo the scale and offset for that slice inside the exported graph.
- constant: fixed values, for example a velocity command [vx, vy, wz].
- qpos, qvel: MuJoCo's full state vectors.
Each item is {term: NAME} with optional scale: X (and relative: true for joint_pos, values: [...] for constant). Anything else (height scans, contact sensors, cameras, a time-varying phase clock, stacked history) cannot come from this list. If the policy needs it, say so in HANDOFF.md, and use the Python route only if it can be done faithfully.

D. The test, as campaign.yaml, with paths relative to the file and no absolute paths. Keys: robot, policy (onnx:policy.onnx, torchscript:policy.pt or module:Attr), base_body, observation, control_hz, duration_s, seeds {sampler, sim, policy}, axes, predicates, search {method: cem or random, budget}, reduce {enabled, max, budget}, report {out: deliverables}.
Axes, each a [low, high] range: push_impulse_ns (a horizontal shove on the base body at t = 1.0 s, along +x), slope_deg, sensor_lag_ms, torque_loss_pct, payload_kg (added to the base body), payload_offset_m (moves that mass along x), friction_mu.
Rules are thresholds on the four signals Teeter records, tilt_deg, height_m, contact_force_n and joint_vel_rads, with a grace time, for example {name: fallen, signal: height_m, op: "<", threshold: 0.12, grace_s: 0.3}.
Propose ranges and rules that fit this robot's size and task, mark them as proposals in HANDOFF.md, and give the reason for each. For scale: an impulse changes the robot's speed by roughly impulse / mass; Teeter's stand-in quadruped weighs 6.02 kg and is tested at 0 to 9 N.s.
Also write runner.yaml, the allowlist a Teeter runner uses (robots: {NAME: robot.xml}, policies: {NAME: onnx:policy.onnx}), and spec.yaml: the same campaign, with robot and policy as those names and no report key.

CHECKS (put the numbers in HANDOFF.md)
1. Export parity: on at least 1000 observations from real rollouts in this project's own simulator, compare the exported policy's output with the training code's own post-processed action. Report the largest absolute difference.
2. Layout parity: for one recorded state, build the observation the way C describes from robot.xml and compare it component by component with the training code's observation of the same state. Report every mismatch.
3. Nominal run: in MuJoCo, with robot.xml and the exported policy, no perturbation, for duration_s at control_hz: the robot should hold its stance (or do its task) without breaking any proposed rule. If it falls, stop and report why: a campaign on a policy that fails with nothing perturbed measures the conversion, not the policy.
If you can install the engine (git clone -b claude/faultline-landing-spec-179f9n https://github.com/Davuddevelop/Faultline.git, then pip install -e "Faultline/harness[onnx]"), also print its index map of your observation and check it against the training code:
python -c "from faultline.model import load; from faultline.observe import ObservationSpec as O; import yaml; c = yaml.safe_load(open('campaign.yaml')); print(O.from_list(c['observation']).describe(load('robot.xml', base_body=c.get('base_body'))))"
then run faultline run campaign.yaml from inside teeter-handoff/, and put its printed summary and the minimal case from deliverables/engineering-report.md in HANDOFF.md. Quote push_impulse_ns and sensor_lag_ms as requested values: they land on the control grid, so the robot receives a rounded amount. A violation count from method cem describes the search, not the robot; only method random supports a failure rate.

FINISH with teeter-handoff/ containing robot.xml (and its meshes), the policy file, campaign.yaml, runner.yaml, spec.yaml and HANDOFF.md, and tell me in a few lines what is UNKNOWN or could not be mapped.
```
