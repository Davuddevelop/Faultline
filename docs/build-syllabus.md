# What you have to know to build this

*3 October 2026. The engineering curriculum: what somebody needs in order to
have written `harness/`, and what they still need for the parts that do not
exist yet. Every API and technique listed was read out of the repository, not
recalled.*

Its companion, `docs/founder-syllabus.md`, is about defending the harness in a
room. This one is about producing it.

---

## The shape of the thing

Strip the domain away and Faultline is three programs stacked:

1. **A deterministic batch simulator.** Load a model, change some physical
   parameters, step it at a fixed rate with a frozen policy in the loop, record
   four scalars per step.
2. **A search loop around it.** Score each run with a continuous severity,
   sample the next batch of points from where the scores were worst, repeat
   within a budget, then relax every failure back toward nominal.
3. **An evidence writer.** Emit artefacts that a hostile stranger can re-run
   and get the same bytes.

Program 1 needs physics and a simulator API. Program 2 needs numerical methods
and statistics. Program 3 needs ordinary but unusually disciplined software
engineering — and it is the one most people underrate, because it is the
product.

---

## 1. Python, at the level this codebase actually uses

Not "learn Python". These specific things, all of which are load-bearing in
`harness/faultline/`:

| Thing | Where, and why it is there |
| --- | --- |
| `@dataclass(frozen=True)` with `__post_init__` validation | `spec.py`, `space.py`, `predicates.py`. A `RunSpec` is immutable because a run that can mutate its own description cannot be reproduced. Validation lives on the object so there is one definition of a valid axis, and the YAML reader does not get a second opinion |
| `typing.Protocol` | `policies.py`. A policy is anything with `reset` and `act`. Structural typing, not inheritance — the customer does not subclass your base class |
| `hashlib` content digests | `spec.py`, `record.py`, `policies.py`, `adapters.py`. Hash the spec, the policy file, the trajectory. This is how "the same run" is defined rather than asserted |
| `@property` for derived values | Everywhere. Keeps one source of truth and no stale duplicate fields |
| `importlib.import_module` for dotted paths | `config.py`. `mypkg.policies:WalkPolicy` in YAML has to become an object. Understand the security implication: this executes the customer's code |
| `concurrent.futures.ProcessPoolExecutor` | `search.py`. Processes, not threads — MuJoCo state is not shareable, and the GIL would make threads pointless anyway |
| `functools.lru_cache` | `reduce.py`, for the model's own friction. Know when caching is safe: pure function of a path |
| `from __future__ import annotations` + full type hints | Every module. Not decoration — it is how a reader knows what a `Trajectory` is without running it |
| `pickle` across the process boundary | `search.py`. Know what is and is not picklable, and why the policy is sent as a payload rather than a live object |

**Learn by:** reading `spec.py` end to end — it is 141 lines and it is the
spine of the whole design. Then `config.py`, which is the same ideas applied to
untrusted input.

**Externally:** *Fluent Python* (Ramalho) for dataclasses, protocols and the
data model. The `concurrent.futures` and `dataclasses` standard-library docs,
read properly rather than skimmed.

---

## 2. NumPy, specifically

A trajectory is arrays. Everything downstream is array work.

Know: arrays against lists and why it matters here; `dtype` and why `float64`
is not optional when the output has to match bit for bit; **C-contiguity**, which
appears twice and for two different reasons: in `adapters.py`, because
TorchScript wants contiguous input; and in `runner.py`, where the trajectory
digest is taken over `ascontiguousarray(arr, dtype=np.float64).tobytes()` —
without pinning both the layout and the dtype, the same trajectory hashes
differently and reproducibility checking silently stops working; vectorised
comparison for predicate evaluation instead of a Python loop over timesteps;
`np.isfinite` for divergence detection; `np.clip` before `arccos`, because a
rotation matrix entry of 1.0000000002 makes it return `nan`.

**And the one that is a correctness issue, not style:** `np.random.default_rng(seed)`,
never the legacy `np.random.seed` global. The codebase uses `default_rng`
throughout (`search.py`, `policies.py`, `space.py`) because a global RNG is
shared mutable state, and shared mutable state across a process pool destroys
reproducibility in a way that is almost impossible to debug afterwards.

---

## 3. MuJoCo as an API

This is the largest single block of specific knowledge, and it is the one no
course teaches — you learn it from the documentation and from reading code.

The exact surface this harness uses:

**Model (static, shared, one per load):** `nq`, `nv`, `nu`, `nbody`, `njnt`,
`nkey`, `opt.timestep`, `opt.gravity`, `body_mass`, `body_ipos`,
`body_inertia`, `body_parentid`, `body_jntadr`, `body_jntnum`, `jnt_type`,
`jnt_qposadr`, `jnt_dofadr`, `geom_friction`, `actuator_forcerange`,
`actuator_gainprm`.

**Data (state, one per run):** `qpos`, `qvel`, `ctrl`, `xpos`, `xmat`,
`xfrc_applied`, `cfrc_ext`, `warning`.

**Functions:** `mj_step`, `mj_resetData`, `mj_resetDataKeyframe`,
`mj_name2id` / `mj_id2name`, `mj_rnePostConstraint`.

**Enums:** `mjtObj`, `mjtJoint`, `mjtWarning`.

The conceptual splits that matter more than the names:

- **Model against data.** Model is the world; data is the state of it. Every
  perturbation in `_apply_perturbation` mutates the *model* before the first
  step, which is why each run needs its own freshly loaded model.
- **Addressing.** `nq ≠ nv` because a free joint is 7 position coordinates and
  6 velocity ones. You index into them through `jnt_qposadr` and `jnt_dofadr`,
  never by counting.
- **`xmat` is a flat 9-vector** you reshape to 3×3. It is body-to-world, so its
  transpose is world-to-body. Tilt is `arccos(R[2,2])`.
- **`xfrc_applied`** is how you push a body: a 6-vector of force and torque in
  world frame, applied every step it is set, cleared when it is not.
- **`cfrc_ext` needs `mj_rnePostConstraint`** to be populated. Reading it
  without that call gives you stale values and you will not notice.
- **`data.warning`** is how a simulation tells you it has diverged. Four classes
  matter, and catching them is the difference between reporting a failure and
  reporting a numerical explosion as a failure.

**Learn by:** the MuJoCo documentation's *Computation* and *XML reference*
chapters, then `harness/faultline/model.py` and `runner.py`. Then write a
50-line script that loads the bundled quadruped, pushes it, and prints tilt per
step — without looking at `runner.py`.

---

## 4. The physics you have to implement, not merely discuss

`docs/founder-syllabus.md` covers what to know for a conversation. These are the
ones where you have to produce correct code:

- **Tilt from a rotation matrix.** `arccos(clip(R[2,2], -1, 1))` in degrees, and
  why the clip is mandatory.
- **Slope by rotating gravity.** Rotate the gravity vector by slope and yaw
  rather than tilting the floor, so contact geometry is identical across runs
  and the only thing varying is the quantity under test.
- **Impulse as force over a window.** An impulse in N·s becomes a force of
  `impulse / window` held for `window` seconds. Understand why a window exists
  at all — an instantaneous impulse destabilises the solver — and that it is
  also the source of the over-delivery defect.
- **Sensor lag as a ring of past observations.** The policy is handed a stale
  observation, indexed back by `round(lag_s * control_hz)` steps. The rounding
  is the quantisation bug.
- **Payload as mass, centre-of-mass shift and inertia scale.** `body_mass`
  increases, `body_ipos` moves toward the offset by the mass-weighted mean, and
  `body_inertia` is scaled by the mass ratio. **That last one is an
  approximation** — the true answer is a parallel-axis correction — and knowing
  the difference is the difference between shipping it knowingly and shipping it
  by accident.
- **Torque loss.** `actuator_forcerange` and `actuator_gainprm[:, 0]` scaled
  together, so both the limit and the response shrink.

**Learn by:** implementing an eighth axis end to end. That exercise is in the
other syllabus too, because it tests both things.

---

## 5. Numerical methods: the search

`search.py` is 413 lines and is the only genuinely algorithmic file.

**Severity.** A signed margin — how far past the threshold the worst moment of
the run got — rather than a boolean. You cannot optimise pass/fail; there is no
gradient of information in a bit. Getting this right is what makes the search
possible at all.

**The Cross-Entropy Method.** Sample a batch from a Gaussian truncated to the
declared box; score; keep the best `elite_frac` (0.25 here); refit mean and
standard deviation to that elite set; repeat. You need to be able to implement
it from the description, and to handle the cases the description omits:

- an elite set where every severity is `-inf`, which makes the refit `nan`
- **variance collapse** — the fitted distribution shrinking to a point and the
  search stopping exploring. The mitigation is a floor, `min_std_frac`, as a
  fraction of each axis's span
- staying inside the declared bounds while sampling from an unbounded Gaussian

**Reduction.** Relaxing each axis back toward nominal while the failure still
fires — a search per axis, with the subtlety that "nominal" for friction comes
from the model rather than from zero, because a slippery-floor failure relaxes
*upward*.

**Determinism under parallelism.** The hard one. The result must not depend on
how many workers ran it, which means the seed belongs to the sample, not to the
worker, and results must be reassembled in submission order.

**Learn by:** implementing CEM from scratch on a 2-D toy function before
reading `search.py`, then comparing. **Externally:** the original cross-entropy
method literature (Rubinstein), and any solid numerical-optimisation text for
the surrounding ideas.

---

## 6. Statistics you have to be able to code

Not cite — implement.

- **Binomial confidence intervals.** Wilson and Clopper–Pearson. Know why the
  naive normal approximation is wrong at the small counts you will actually have.
- **The rule of three.** Zero failures in *n* runs gives an upper 95% bound of
  about 3/*n*.
- **Why directed samples break all of it**, and how to make code *refuse* to
  compute a rate from them. The calculator should error, not warn.
- **Prediction-powered inference**, for Layer 2. This is the one you cannot do
  yet, it is the moat, and it is a real implementation project rather than a
  library call.

**Learn by:** building the calculator (exercise 4 in the other syllabus). It is
the first brick of Layer 2 and it is maybe 150 lines.

---

## 7. The engineering discipline that *is* the product

This is the part that separates a harness from evidence, and it is mostly not
glamorous.

- **Determinism as a design constraint**, not a test. Three separate seeds —
  sampler, sim, policy — so a divergence can be attributed rather than argued
  about. No wall-clock, no global RNG, no set iteration order, no unordered
  parallel results.
- **Provenance capture.** `sim_environment()` records MuJoCo, NumPy, Python and
  platform with every run. A result without its environment is not reproducible
  and therefore is not evidence.
- **Exact dependency pinning.** `mujoco==3.12.0`, not `>=`. Contact solvers
  change between minor versions.
- **Content hashing.** Hash the spec, hash the policy file, hash the
  trajectory. Then `replay` can *prove* a re-run matched rather than claim it.
- **Archive format choices.** JSONL for the manifest (appendable, streamable,
  greppable), JSON for structured reports, CSV for traces. No database — a file
  tree is auditable by someone who does not trust you, and that is the whole
  point. Note also the care in `write_archive` to delete stale `mode-N.csv`
  files: an archive that disagrees with its own `report.json` is worse than no
  archive.
- **Failing loudly.** `ReductionError` exists so a failed reduction cannot
  return something that looks like a reduction. `PolicyLoadError` explains that a
  plain `state_dict` is not a TorchScript archive and says how to export one.
  Error messages are a feature when your user is an engineer who will not file a
  ticket.
- **Tests as the only licence to claim anything.** 168 of them; 164 pass and 4
  skip, in 99 seconds. Run them before believing any claim, including mine.

**Externally:** this is mostly learned by reading good code and by being burnt.
*A Philosophy of Software Design* (Ousterhout) is the shortest useful book on
the design side.

---

## 8. Packaging and interface

Small but genuinely needed, and all present in the repo:

- `pyproject.toml` with a dynamic version read from `__init__`, one source of
  truth
- **optional extras** (`[onnx]`, `[torch]`) so someone testing an ONNX policy is
  not made to install PyTorch, with imports deferred into the constructor so the
  error arrives as a sentence rather than an ImportError at module load
- a console entry point, and `argparse` subcommands: `init`, `run`, `replay`,
  `version`
- **YAML schema design** — key sets validated explicitly so a typo is an error
  rather than a silently ignored setting

---

## 9. What you do not yet know, because it is not built

Each of these is a named gap with a named body of knowledge behind it.

| To build | You will need |
| --- | --- |
| **`faultline diff`** (roadmap A5, the Layer 1 wedge) | Set arithmetic over failure modes; a definition of when two modes are "the same"; and comparability gating — refusing to diff two campaigns whose spaces, predicates or model differ. The hard part is the definition, not the code |
| **Layer 2, the calibrated estimate** | Prediction-powered inference, implemented. Experimental design for paired sim/real runs. Enough statistics to defend the bound, not just produce it |
| **Video per flagged run** | MuJoCo offscreen rendering: EGL or OSMesa, `MjrContext`, framebuffers, and ffmpeg encoding. Be warned — all three GL backends fail in this container, which is why `media/` draws from captured geometry instead |
| **PDF deliverables** | A typesetting pipeline. Markdown → PDF via Pandoc/LaTeX or Typst. Mostly a tooling decision, not a knowledge gap |
| **Campaigns at real scale** | 150 runs on one machine is not evaluation. Containerisation, a job queue, cloud cost modelling, and keeping determinism across machines with different CPUs |
| **Anything hosted** | A web backend, auth, and storage of customer artefacts — which drags in the security posture in `docs/founder-brief.md` §4. Avoid as long as possible; "they run it, you read the archive" needs none of it |
| **More robot classes** | Humanoids and arms: more DOF, different contact regimes, different failure predicates. Mostly `model.py` and `observe.py` work |

---

## 10. What you do not need

| Skip | Why |
| --- | --- |
| Web frameworks | The site is static HTML. The product is a CLI |
| Databases | The archive is a file tree, deliberately |
| Kubernetes, microservices | You have one machine and no users |
| GPUs and CUDA | MuJoCo runs on CPU; a frozen policy's forward pass is tiny |
| C++ and MuJoCo internals | The Python bindings cover the entire surface above. Revisit only if you need a feature the bindings do not expose |
| Training infrastructure | You load frozen checkpoints. You never train |

---

## 11. The order, and what to build at each step

Each step is a thing you build, not a thing you read.

1. **Python and NumPy to the level in §1–2** — reread `spec.py` and `config.py`
   until every decision in them looks inevitable rather than arbitrary.
2. **MuJoCo from the documentation** — write the 50-line push-and-print script
   without looking at `runner.py`.
3. **The eighth axis** — registry, perturbation, reduction, test. This is the
   exercise that proves §3 and §4 together.
4. **CEM from scratch on a toy function** — then read `search.py` and find what
   you missed. You will have missed the variance floor.
5. **The confidence-interval calculator** — §6, and the first piece of Layer 2.
6. **Fix the impulse over-delivery**, with the test that would have caught it.
   Real defect, real fix, and it makes every impulse number on the site truer.
7. **`faultline diff`** — the most commercially valuable thing on this list, and
   the one where the design is harder than the implementation.

Items 3, 5, 6 and 7 leave the repository better than they found it. That is the
point: at this stage you have no reason to learn anything you cannot immediately
spend.
