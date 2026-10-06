# Faultline — what the founder has to know

*Written 3 October 2026. Everything factual in here was checked against the
repository on that date; the commands to re-check are given so this file can be
audited rather than believed.*

The other documents answer different questions, and this one does not repeat
them:

| Document | Answers |
| --- | --- |
| `docs/strategy.md` | Why this is a company — market, three layers, competition, pricing, risks |
| `docs/roadmap.md` | What to build, in what order, over 12 months |
| `docs/product-spec.md` | What each layer must do and must never claim |
| `docs/primer.md` | The domain, from scratch |
| `docs/learning-path.md` | What to learn, as a learner |
| **this file** | What is actually true today, what nobody else has written down, and what only you can do |

---

## 1. Ground truth, verified

Not what the site says. What the code does, on 3 October 2026.

| | |
| --- | --- |
| Harness | 4,917 lines of Python across `harness/`, of which 2,909 are the package |
| Tests | 168 collected — **164 pass, 4 skip**, in 99 s (run 6 Oct 2026) |
| Searchable axes | **7** — `push_impulse_ns`, `slope_deg`, `sensor_lag_ms`, `torque_loss_pct`, `payload_kg`, `payload_offset_m`, `friction_mu` |
| Trajectory signals | 4 — `tilt_deg`, `height_m`, `contact_force_n`, `joint_vel_rads` |
| Simulator | MuJoCo, pinned exactly at 3.12.0 |
| Model formats | MJCF, and URDF with a warning that it carries no contact parameters or actuator dynamics |
| Policy formats | ONNX and TorchScript, both as optional extras |
| CLI | `init`, `run`, `replay`, `version` |
| Parallelism | Real — `ProcessPoolExecutor`, `workers` in the config |
| Deliverables | `engineering-report.md`, `safety-appendix.md`, `archive/` (`manifest.jsonl`, `campaign.json`, `report.json`, `traces/mode-N.csv`) |
| Published campaign | 150 evaluations, 51 violations, 10 reduced, 87/4096 cells, 2026-08-22 |
| Independently reproduced | First breach at 1.26 s, recomputed from physics by `media/capture_sim.py` |

Re-check any of it:

```sh
grep -A 10 'SEVERITY_AXES: tuple' harness/faultline/reduce.py
find harness -name '*.py' -not -path '*__pycache__*' | xargs wc -l | tail -1
grep -n 'add_parser' harness/faultline/cli.py

cd harness && python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && python3 -m pytest tests/ -q
```

**The suite has now actually been run**, which earlier versions of this file
could not say. In a clean virtual environment, `pip install -e ".[dev]"` then
`python -m pytest tests/ -q` gives 164 passed, 4 skipped, in 99 seconds. A full
120-simulation campaign via `faultline init` and `faultline run` takes about 13
seconds. Both were verified on 6 October 2026 — re-run them before trusting any
later claim, including mine.

### Numbers that have already drifted

This has happened repeatedly, which is why rule 4 in `CLAUDE.md` exists.

- `docs/strategy.md` §1 says **ten physical axes**. There are seven.
- `docs/strategy.md` §1 says **3,514 lines and 110 tests**. It is now 4,917 and 131.
- `index.html` quotes a minimal case of **7.96 N·s on a 0–16 range** and a
  sampled failure band of **9.68–15.49**. Neither is in
  `assets/data/campaign.json`, which records 7.875 on a 0–9 range and a band of
  8.673–9.000. Those figures came from a campaign that is not in the repo.

Fix the first two by editing. The third is already fixed in `ink/`, which takes
every figure from the campaign record by machine.

### Things the site claims that the code does not do

Both the old page and the ink cut carry this copy, and it is not true today:

| Claimed | Reality |
| --- | --- |
| Simulators: MuJoCo, **Isaac Sim** | No Isaac Sim code exists anywhere in `harness/` |
| Output: **PDF** | Output is Markdown |
| Output: **ROS 2 bags** | No ROS code exists |
| Output: **MP4 per flagged run** | No video writer exists; `media/` renders video by a separate, hand-written path |
| Predicates: **Python for anything the schema can't express** | There is no escape hatch. `Predicate` in `spec.py` is exactly `signal`, `op` (`>` or `<`), `threshold`, `grace_s` |

`index.html` also lists predicate forms that do not exist: centre of mass
leaving a safe set, per-link contact force, and recovery within `t_recover` of
a disturbance. None are implementable against the four signals the runner
computes.

This is the exact failure mode the standing rules exist to prevent, and I
carried most of it from the old page into `ink/` without checking. **The `ink/`
interfaces block is now corrected** to describe what the code does. `index.html`
is not — fix or delete those claims before anyone technical reads it. A robotics
engineer will ask about Isaac Sim in the first call, and "not yet" after you
listed it is worse than never having listed it.

---

## 2. The repository is public, with no licence

`github.com/Davuddevelop/Faultline` is **public**. No `LICENSE` file; the
package declares `UNLICENSED`.

What that means in practice:

- Anyone can read the harness, `docs/strategy.md` — including your pricing
  table, your stated moat and your assessment of Foretellix and Applied
  Intuition — and `docs/roadmap.md`.
- No licence means default copyright, so nobody may legally copy the code. It
  does not stop anyone reading the thesis and acting on it.
- Open by default is a legitimate strategy, and for a solo unknown founder it
  is often the right one: it is the cheapest credibility you will ever get, and
  the harness being readable is most of your evidence that you can build.

The decision to make consciously, this week: **the code can stay public; the
strategy document probably should not.** Move `docs/strategy.md` and
`docs/roadmap.md` into a private repository, or accept that competitors read
them. Do not leave it unconsidered.

---

## 3. The one thing that gates everything

Nobody outside this repository has ever run a campaign.

Everything shown publicly is one campaign, against a quadruped model you wrote,
driven by a stand-in policy you wrote, at 150 evaluations on one machine. The
harness is real and the evidence chain is real. What is untested is whether any
of it is *useful to someone who is not you*.

`docs/strategy.md` §8 already names the artifact that matters: a failure mode
found in a real customer's policy that they did not know about, which they then
reproduced on hardware. Until that sentence is true, every other activity —
more axes, better reports, a nicer landing page, the calibration layer — is
building on an untested assumption.

**The implication for how you spend time:** you are not short of engineering.
You are short of contact with the people who would buy. The next unit of work
with the highest information value is ten conversations, not ten commits.

---

## 4. Why they will not send you a checkpoint, and what to do about it

This is the biggest practical obstacle in the business and it is in none of the
other documents.

A trained policy checkpoint is among the most valuable artifacts a robotics
company owns. It encodes millions of dollars of training compute, data
collection and reward engineering. Asking a company to upload one to a
pre-product, single-person operation in Azerbaijan is asking for something they
will refuse by reflex, regardless of how good the harness is, and their
security team will refuse it for them.

Three ways around it, in the order you should offer them:

1. **They run it, you never see it.** The harness is a pip-installable package.
   They run `faultline run campaign.yaml` inside their own infrastructure and
   send you the archive — `report.json`, `manifest.jsonl`, the traces. The
   archive contains results, not weights. This requires nothing new to build,
   removes the objection entirely, and is how your first three engagements
   should work.
2. **They send an exported ONNX graph for a policy they have already shipped or
   retired.** Lower value to them, still real for you.
3. **They send a current checkpoint under a written agreement.** Only once you
   are an entity that can sign one, with a no-retention and no-derivative-use
   clause. Not the first conversation; possibly not the first year.

Option 1 also inverts the sales motion in your favour: you are not asking for
their crown jewels, you are asking them to run a command and show you the
output. Build the quick-start around that path, and make it work on a laptop
without a GPU.

What you must be able to answer when asked, and should write down before the
first call: where their data lives, who else can see it, what you retain after
an engagement ends, and what happens to it if you stop working on this.

---

## 5. Legal and operational reality

None of this is urgent today. All of it becomes urgent exactly when something
good happens, which is the wrong moment to discover it.

**Capacity to contract.** If you are under 18, you cannot in most jurisdictions
be a company director or sign a binding commercial contract on your own. This
is not a reason to stop; it is a reason to know the sequence. Everything up to
and including unpaid design-partner work and running campaigns can be done as
yourself. The moment money or a signed agreement is involved, you need an adult
co-signer — a parent, a guardian, or a co-founder — named properly rather than
improvised. Decide who that is before you need them.

**Entity.** You do not need one to have ten conversations. You need one to
invoice. `docs/strategy.md` §7 already flags that an EU entity is likely a
precondition for Layer 3 being sellable at all — a notified body's client
wanting evidence from a non-EU supplier is friction you cannot argue away.
Estonian e-Residency is the common route for exactly this situation and is
worth researching before you need it, not after.

**Payments.** Receiving EU money into Azerbaijan as an individual is solvable
but slow, and your first customer will not wait. Have the route figured out in
advance.

**Export and dual use.** Robotics testing tooling is not obviously
export-controlled, but "software that evaluates autonomous machine safety" is
close enough to categories that get regulated that you should check rather than
assume, before selling internationally.

**Insurance and liability.** The day you tell a manufacturer their policy is
adequately tested, you have acquired liability. This is the real reason the
standing rule exists — never say safe, verified, validated, certified or
compliant. It is not only honesty. It is the thing that keeps you from being
named when a robot injures someone. Keep it in the contract as well as on the
website: you report findings, you do not certify.

---

## 6. Money

Pre-revenue, this costs almost nothing to run, and that is a strategic asset.
Your runway is measured in years rather than months, so you can afford to be
slow and right.

Current costs: a domain, and compute if you ever run campaigns at scale. The
site is static. The fonts are self-hosted and free. The harness runs on CPU.

What that buys you: the ability to say no. You do not need a customer this
quarter, so you can refuse a bad first customer, refuse to overstate the
product to close something, and refuse an investor who wants the category to
arrive faster than it will.

The pricing table in `docs/strategy.md` §6 is explicitly estimates anchored on
AV deal sizes. Treat the first three real quotes as the experiment that
replaces it. Expect to be wrong about at least one tier — most likely the
certification pack, which depends on a delegated act nobody has written.

---

## 7. What you have to own personally

Delegable eventually: implementation, the website, report formatting, infra.

Not delegable, now or later:

1. **What the product may claim.** Every pressure in this business pushes
   towards overstatement — a customer wants a clean verdict, an investor wants
   a bigger number, a landing page wants a stronger line. You are the only
   person who can hold that line, and the company is worthless the first time
   it slips in a document someone relies on.
2. **The physics being right.** You do not have to have written every solver,
   but you must be able to say why a result is trustworthy and where it is not.
   This is why the learning is not optional — not to build the harness, but to
   defend it in a room with someone who has shipped robots for fifteen years.
3. **Customer conversations.** Nobody else can hear the objection you did not
   anticipate.
4. **Deciding what not to build.** The roadmap's "explicitly not doing yet"
   section is doing more work than the rest of it.

---

## 8. Decision rules, set now while it is cheap

Write these down before you are emotionally invested in the answer.

**Continue if, by the end of the next 90 days:** at least two teams shipping
learned policies have taken a real call; at least one has run the harness on
their own robot; you have found at least one failure mode in something you did
not write.

**Pivot the wedge if:** teams consistently say the regression-testing problem
is already solved internally and they do not care about evidence. That tells
you Layer 1 is not the wedge, and the business is the evidence layer alone —
which is a slower, more regulatory, more EU-entity-shaped company. Know in
advance that you would accept that.

**Stop if:** you cannot get conversations at all over two serious attempts, or
simulated failures reliably fail to reproduce on hardware once you can test
that. The second is the existential one named in `docs/strategy.md` §7.1.

**Do not use as a stop signal:** slow progress, no revenue in year one, or a
competitor announcing something adjacent. All three are expected.

---

## 9. What to measure now

Vanity metrics do not exist yet, which is useful. Count only:

- Conversations with people who ship learned policies into production
- Campaigns run by someone who is not you
- Failure modes found in a policy you did not write
- Failures reproduced on hardware
- Numbers on the website that cannot be traced to a file in the repository
  (target: zero — `tools/build_ink_figures.py` enforces this for `ink/`)

---

## 10. The learning, reordered for the business

`docs/learning-path.md` is the right path for becoming a roboticist. The order
that unblocks *the company* is different, because the harness treats the policy
as frozen and opaque — you do not need to be able to train one to test one.

1. **Control theory and simulation fidelity** — load-bearing today. You already
   found the impulse over-delivery and the sensor-lag quantisation yourself;
   those are exactly the questions a customer's engineer will ask.
2. **Statistics and evidence** — load-bearing for Layer 2, which is the moat.
   Prediction-powered inference, confidence intervals, what a sample licenses.
   This is the part no robotics team wants to staff, which is precisely why it
   is defensible.
3. **Contact dynamics and sim-to-real** — needed to answer "your simulator is
   wrong" with something better than agreement.
4. **RL itself** — needed to speak the customer's language and map their
   observation contract. Genuinely useful, genuinely not the bottleneck.
5. **Hardware and electronics** — the furthest from the business, and the most
   fun. Guard against doing it first for that reason.

---

## 11. Open technical debt

Known, documented, unfixed. A customer's engineer may find any of these, and it
is much better if you name them first.

- **Impulse over-delivery.** The requested impulse is spread over 0.05 s but
  applied on the 0.02 s control grid, over-delivering by roughly 20% at the
  default push time. This is why every impulse is quoted as *requested*.
- **Sensor-lag quantisation.** Lag rounds half-to-even onto the control grid,
  so the delivered lag is not monotonic in the requested value.
- **No `faultline diff`.** The Layer 1 product surface in `docs/roadmap.md` A5
  — the checkpoint-versus-checkpoint verdict that is supposed to be the wedge —
  does not exist yet.
- **Coverage is reported on a 4-bin grid**, which is a coarse measure of a
  continuous volume. 87/4096 cells is honest and also not very informative.
- **One robot class.** Everything is validated against one quadruped.

---

## 12. The question to answer in 30 days

Not "is the harness good" — it is better than it needs to be for this stage.

> Will anyone who ships a learned policy into the EU take a call, and when they
> do, what do they say they need before January 2027?

Ten conversations answers it. If the answer is nobody, you learned it in a
month. If the answer is two, the rest of this document starts to matter.
