# Skills

Project skills for this repo. Claude loads the `name` and `description` from
each `SKILL.md` at session start and reads the body only when a task matches,
so the standing cost is the descriptions (~1k tokens), not the content.

## Where these came from

**25 skills installed.** Counted from `metadata.origin` in each `SKILL.md`, so
these numbers can be re-derived rather than trusted:

| Source | Licence | Skills |
| --- | --- | --- |
| [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code), tagged `ECC` | MIT (see `LICENSE-everything-claude-code`) | 12 |
| Tagged `community` | see upstream | 3 |
| Written for this repo | — | 7 (the domain set, below) |
| Untagged — `benchmark-methodology`, `frontend-design`, `motion-foundations` | see each file | 3 |

`frontend-design` is Anthropic's, from [`anthropics/skills`](https://github.com/anthropics/skills).
The other two untagged ones predate this accounting and should get an `origin`
when someone next touches them.

ECC ships 286 skills. Most are for stacks this project does not use (Laravel,
Django, healthcare, DeFi, logistics); installing them would cost context on
every turn and widen the surface of instructions Claude follows for no return.

## Why the domain skills were written rather than installed

Searched, 2026-09-04, for existing skills covering maths, physics, control
theory and RL fundamentals. Nothing usable exists:

| Source | Result |
| --- | --- |
| claude.ai skill library | empty |
| Plugin marketplace | Unity (game-engine collision) and DataRobot (AutoML) only |
| ECC, 286 skills | nothing on maths, physics, control or RL theory |
| [`arpitg1304/robotics-agent-skills`](https://github.com/arpitg1304/robotics-agent-skills) | 10 skills, all ROS1/ROS2 plumbing; explicitly no control theory, kinematics or dynamics — and this project does not use ROS |
| [`NVIDIA/skills`](https://github.com/nvidia/skills), 500+ | no Isaac Lab, Isaac Sim, MuJoCo, locomotion or sim-to-real; its `nemo-rl-*` skills are RLHF for language models, a different subject |

The published ecosystem is vendor product skills and ROS boilerplate. The
fundamentals are unwritten, so the seven below were written against this repo's
code, with every claim traced to a file and line or to a measured number.

## What is installed, and why

**Design — against generic output**
- `frontend-design` — Anthropic's canonical frontend design skill
- `frontend-design-direction` — pick a direction before coding: purpose,
  audience, tone, one memorable detail
- `make-interfaces-feel-better` — concentric radii, optical alignment, text
  wrapping, hit areas, interaction states
- `design-system` — consistency audits and styling review
- `motion-foundations` — motion tokens, spring presets, reduced-motion safety
- `accessibility` — WCAG 2.2 AA

**Working sessions**
- `context-budget` — audit what is eating the context window
- `token-budget-advisor` — cost-aware planning
- `strategic-compact` — compact at phase boundaries rather than arbitrarily
- `verification-loop` — verify before claiming work is complete

**Engineering rigour**
- `architecture-decision-records` — capture decisions as they are made
- `recursive-decision-ledger` — repeated rollouts, stochastic search,
  local-optima exploration (relevant to adversarial search itself)
- `benchmark-methodology` — comparing methods without fooling yourself
- `error-handling` — typed errors, retries, circuit breakers

**The domain — written for this repo, grounded in its code**
- `robot-policy-testing` — reproducibility, predicates, reduction, sim-to-real,
  the regulatory framing
- `spatial-maths-and-frames` — rotations, SO(3), quaternion ordering, world vs
  body frame, where `arccos` loses precision
- `rigid-body-dynamics` — `qpos`/`qvel` and why they differ in length, joint
  types and DOF addressing, inertia, contact and friction, how a run diverges
- `control-theory` — control rate vs physics rate, actuators, sensor latency,
  and the quantisation that makes a requested impulse differ from the delivered
  one
- `rl-for-robot-policies` — MDPs, PPO, the observation layout as a contract,
  domain randomisation vs test-time perturbation, why coverage means nothing
  for a network
- `optimisation-and-search` — severity as a signed objective, the Cross-Entropy
  Method, variance collapse, why a directed hit rate is not a failure rate
- `uncertainty-and-evidence` — binomial intervals, the rule of three, coverage
  vs confidence, prediction-powered inference, the claims ladder

**Machines**
- `latency-critical-systems` — realtime and streaming constraints
- `cpp-coding-standards` — C++ Core Guidelines
- `python-patterns` — idioms, typing, PEP 8
- `pytorch-patterns` — reproducible training pipelines and data loading

## Deliberately not installed

- `taste` — reads as design taste; is actually creative direction for
  hyperpop music videos
- `repo-scan` — a bootstrap that fetches and installs a skill from a remote
  commit at runtime
- `tdd-workflow` — pipes remote content into a shell
- `deep-research`, `search-first` — depend on MCP servers and sub-agents this
  setup does not have

## Adding more

Vet before installing. A skill is instructions Claude will follow later, so
read the body rather than trusting the description, and check for anything that
fetches code at runtime or reaches for credentials:

```
grep -rlE 'curl [^|]*\| *(ba)?sh|npx +-y|\.env|API_KEY|~/\.ssh' <skill-dir>
```
