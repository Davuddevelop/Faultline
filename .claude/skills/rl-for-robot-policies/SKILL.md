---
name: rl-for-robot-policies
description: Reinforcement learning as it applies to robot control — MDPs, policy and value, PPO, observation and action spaces as a contract, reward shaping, domain randomisation vs test-time perturbation, distribution shift, and why code coverage is meaningless for a neural network. Use when reading observe.py or adapters.py, mapping a customer's observation layout, discussing how a policy was trained, or explaining why traditional software testing does not transfer.
metadata:
  origin: written for this repo
---

# RL for robot policies

Faultline never trains anything. It runs frozen policies and looks for the
conditions under which they fail. But you cannot test a policy competently
without knowing how it was made, because every assumption the training made
becomes a way the deployed policy can break.

## The setup

A control problem is framed as a **Markov decision process**: at each step the
agent observes a state, takes an action, receives a reward, and the world moves
on. "Markov" means the current state is sufficient — history adds nothing. This
is an assumption, and for real robots it is usually false (motor temperature,
gear wear, contact history all persist), which is one reason simulated policies
surprise people on hardware.

- **Policy** `π(a|s)` — the thing under test. A neural network mapping
  observation to action.
- **Value** `V(s)` — expected future return from a state. Used during training
  to reduce gradient variance; usually discarded before deployment.
- **Return** — discounted sum of future rewards, `Σ γᵗ r`. The discount `γ`
  sets the horizon the policy cares about.

**PPO** (Proximal Policy Optimisation) is what most locomotion policies are
trained with. It is on-policy and takes conservative steps by clipping how far
the updated policy may move from the previous one.

A caution worth holding onto: PPO also appears in LLM training (RLHF), but that
is a **different problem**. There the "environment" is a single-turn text
completion and the reward comes from a learned preference model. Robot RL has
genuine environment dynamics, long horizons, and a reward you write by hand.
Papers and intuitions do not transfer freely between the two. NVIDIA's
`nemo-rl-*` skills, for instance, are RLHF for language models and are not
about robot control.

## The observation is a contract

This is where a testing harness most easily produces garbage. A policy is a
function of **a specific vector, in a specific order, with specific units and
scaling**. Feed it a different layout and it does not raise — it returns
confident, wrong actions, and the campaign reports failures belonging to the
harness rather than the robot.

The harness therefore declares the layout explicitly (`observe.py`), following
**Isaac Lab and legged_gym** naming, since that is what most locomotion
policies are trained against. `ObservationSpec.default()` is:

```python
Term("projected_gravity"),          # which way is down, in the robot's frame
Term("base_ang_vel"),               # how fast it is rotating
Term("joint_pos", relative=True),   # joint angles, offset by the default pose
Term("joint_vel", scale=0.05),      # joint speeds, scaled down
```

Two of those choices carry real content:

**`relative=True`** subtracts `m.qpos0` — the model's default pose. Policies
learn *offsets from a nominal stance*, not absolute joint angles. Feed absolute
angles to a policy trained on relative ones and every output is biased.

**`scale=0.05`** is observation normalisation. Joint velocities are numerically
much larger than joint angles, and a network trained on inputs of wildly
different magnitudes trains badly. The training code applied this scale; the
harness must apply the same one or the policy sees velocities twenty times too
large.

`prev_action` deserves a mention: it gives a feedforward policy a one-step
memory of what it just did, which is how most locomotion policies get temporal
context without being recurrent.

**Before running a campaign, diff the layout.** `ObservationSpec.describe()`
prints it index by index precisely so this can be checked against the customer's
training code rather than assumed.

## Domain randomisation is not the same as our perturbations

Both vary physics parameters, so they get conflated. The difference is when:

- **Domain randomisation is training-time.** The policy is trained across a
  distribution of frictions, masses and latencies so it learns something robust
  to all of them. The policy *sees* this variation and adapts to it.
- **Our perturbation axes are test-time.** The policy is frozen. We are asking
  where it breaks.

The useful consequence: if a customer randomised friction over `[0.4, 1.0]`
during training, failures we find inside that range are more interesting than
failures outside it. Inside the range means the training did not achieve what
it intended. Outside means we are testing beyond what was ever claimed — still
worth reporting, but a different claim. **Always ask what was randomised during
training, and over what ranges.**

## Distribution shift

The dominant failure mechanism. A policy is reliable on the distribution of
situations it was trained on, and offers no guarantee anywhere else. Nothing in
the network signals "this input is unlike my training data" — it extrapolates
silently and confidently.

This is why the interesting failures sit in *corners*: moderate slope **and**
moderate latency **and** a payload slightly off centre, none individually
outside the training range, jointly a situation never seen.

## Why coverage means nothing here

This is the idea the whole product rests on, so it is worth stating precisely.

Testing ordinary software works because a program has **branches**. They are
finite, enumerable, and "100% branch coverage" is a meaningful claim about
having exercised every path.

A neural network has no branches. It is a continuous function. There is no
finite set of paths to enumerate, so:

- Line coverage of the inference code is trivially 100% after one run and tells
  you nothing.
- The space of situations is a **continuous volume**, not a list of cases.
- A hundred scripted scenarios tell you about a hundred points in that volume,
  and nothing about the space between them.

So the question changes from "did we execute every path" to "where in this
volume does the policy break, and how much of the volume did we look at."
Coverage becomes a claim about the **declared parameter space** — and only
that. It is never a claim about safety.

## Loading a frozen policy

`adapters.py` supports ONNX and TorchScript exports, and enforces two things:

**Determinism.** `_assert_deterministic` runs the same probe observation twice
and refuses the policy if the outputs differ. This catches the classic export
bug: dropout or batch-norm left in training mode. A stochastic policy makes
every campaign result unreproducible, which makes it not evidence.

**Content-addressed identity.** The policy id is `f"{path.stem}@{sha256[:12]}"`
— derived from the file's contents, not its path, because paths get overwritten
and `latest.onnx` is not an identifier.

Two deliberate restrictions:

- `intra_op_num_threads = 1`, because thread count changes floating-point
  summation order and therefore the result.
- Multi-input ONNX models are refused. That signature usually means a recurrent
  policy carrying hidden state, and hidden state across runs would break the
  independence the search assumes.

## Related

`spatial-maths-and-frames` covers the frames observation terms live in.
`uncertainty-and-evidence` covers what a campaign's results actually license
you to claim. `robot-policy-testing` covers the sim-to-real gap.
