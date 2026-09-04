# Learn links

Every topic in the roadmap, with where to actually learn it.
*Companion to ROADMAP.md. This file is study material only. Gates and rules live
in the other file.*

This is your plan, reviewed. The structure, the gate ordering and the resource
choices are yours and mostly stand. What I changed is listed in the next
section so you can audit every edit rather than trusting the diff.

---

## What I changed, and why

**1. The hours do not fit in five to six months.** This is the important one.
See *Budget* below — the plan is roughly 480–1000 hours of study. At 20 h/week
that is 6–12 months; five months only works at close to full-time and only if
Gate 4 goes well, which it usually does not. Nothing here is wrong. There is
just more of it than the window holds, so you have a choice to make and I have
laid out two named paths rather than picking for you.

**2. Maths was the thinnest section, and it is what you asked for.** The
original had two entries — 3Blue1Brown as an optional fallback, and Modern
Robotics ch 1–3. No probability, no statistics, no optimisation, no numerical
methods. RL is built on expectations and variance; Faultline's whole evidence
layer is confidence intervals. Added as a standing track that runs across all
gates rather than sitting in one.

**3. Physics was missing as a subject.** MuJoCo's documentation is a manual, and
Modern Robotics ch 1–3 is *kinematics* — where things are, not what forces do.
Nothing covered dynamics or contact. Contact and friction dominate the
sim-to-real gap, which is Gate 4's entire subject, so you would have arrived at
Gate 4 without the physics Gate 4 is about. Added ch 8 to Gate 2 and ch 11–12
plus contact material to Gate 3.

**4. Sutton & Barto 3, 6, 13 skips 9–10.** Those two chapters are the bridge
from tabular RL to deep RL — why a neural network can stand in for a value
table at all. Jumping 6 → 13 leaves a hole exactly where "deep" enters "deep
RL." Added.

**5. Nothing taught evaluation.** Gates 3 and 4 train and deploy; nothing said
how to know whether a policy is *good*. That is your own company's subject and
it was absent from your own study plan. Added to Gate 3, and it is the cheapest
gap here to close because `docs/primer.md` already covers most of it.

**6. Added a warning on Bittle sim-to-real.** Not to discourage it — to stop
Gate 4 becoming an unbudgeted wall. Details in that gate.

**7. Verified: Lyrical Luth.** May 2026, LTS, supported to 2031. Your note was
correct and is unchanged.

**8. Link fix.** The Hugging Face robotics course canonical path includes
`/en/`, and it starts at unit 0, not unit 1.

### On link verification — read this

Your header says "the primary sources below are verified." I could **not**
re-verify them from here: this environment's network policy blocks almost all
outbound domains, so every check returned a proxy error rather than a real
status code. I am not going to describe that as an audit.

What that means for you:

- Links I confirmed through search: MuJoCo Playground (`playground.mujoco.org`
  is correct), the Hugging Face robotics course, and the ROS 2 Lyrical Luth
  dates.
- Everything else is **unverified from here** — carried over from your file
  as-is. They may well all be fine; I just did not check them and will not say
  I did.
- Links I added are given with **title and author first, URL second**, so a
  moved URL costs you a search rather than a dead end.

---

## Budget — read before anything else

Rough hours, assuming you do the exercises rather than watching passively. These
are estimates from scope, not measurements.

| Gate | Hours | What dominates |
| --- | --- | --- |
| 1 — Electronics + C | 120–200 | K&R with the exercises is most of it |
| 2 — Control | 80–140 | implementing PID properly, not watching lectures |
| 3 — Simulation + RL | 150–250 | writing PPO yourself, then debugging it |
| 4 — Sim to real | 120–400+ | open-ended; see the warning in that gate |
| 5 — Business | 10–20 | deliberately small |
| **Total** | **480–1010** | |

| At | Elapsed |
| --- | --- |
| 15 h/week | 8–17 months |
| 20 h/week | 6–12 months |
| 35 h/week | 3.5–7 months |

So: **five to six months is reachable only near full-time, at the optimistic end
of every estimate, with Gate 4 going smoothly.** Plan for that and a normal
setback becomes a failure. Two honest options:

**Path A — Faultline first.** Reorder to **3 → 2 → 4 → 1 → 5**. Faultline is
Python, MuJoCo, RL and statistics; Gate 3 is the one that lets you co-engineer
it, and in your current order it sits third behind ~200 hours that do not touch
it. This gets you to real design conversations in about 5–6 months.

**Path B — Robotics first.** Your current order, unchanged, at 10–12 months.
This is not the worse plan. It makes you an actual robotics engineer rather than
someone who can only reason in simulation, and the Bittle gives you hardware to
test against — which Faultline needs eventually anyway. It just costs twice as
long before you can push back on me.

Pick deliberately. The failure mode is picking B and *believing* it is A.

---

## The maths track — runs across all gates

New section. Do it in parallel, roughly 3–4 h/week, not as a separate gate. You
never "finish" this; you go back to it when something stops making sense.

**The one book to own**

- ***Mathematics for Machine Learning*** — Deisenroth, Faisal, Ong. Free PDF,
  `mml-book.github.io`. This is exactly the right book for your position: linear
  algebra, calculus, probability and optimisation in one place, aimed at someone
  who needs to *use* them. Part I is the whole foundation.

**Linear algebra** (Gate 2 onward — you need this for frames)

- **3Blue1Brown — Essence of Linear Algebra.** Watch first, for intuition.
- MML Part I ch 2–4 for the actual mechanics.
- Why it matters here: a rotation matrix is orthonormal, which is why its
  transpose is its inverse, which is why `R.T @ v` appears everywhere in
  `harness/faultline/observe.py`. See the `spatial-maths-and-frames` skill.

**Calculus and optimisation** (before Gate 3)

- **3Blue1Brown — Essence of Calculus.**
- MML ch 5 (vector calculus) and ch 7 (continuous optimisation).
- Why: policy gradients *are* calculus. Karpathy teaches you to implement
  backprop, which is not the same as understanding what the gradient is.

**Probability and statistics** (before Gate 3, and the most neglected)

- **Seeing Theory** (Brown University) — visual, free, an afternoon well spent.
- ***Introduction to Probability*** — Blitzstein & Hwang (Harvard Stat 110).
  Free book plus a full lecture series. The best available treatment.
- ***Think Stats*** / ***Think Bayes*** — Allen Downey. Free, Python-first,
  practical.
- Why: RL is expectations and variance throughout. And Faultline's entire
  evidence claim is statistical — if you cannot say what "zero failures in 300
  runs" bounds the failure rate to, you cannot defend your own product. (It is
  about 1%. The rule of three: `3/n`.) See the `uncertainty-and-evidence` skill.

**Numerical methods** (during Gate 3)

- **Goldberg — *What Every Computer Scientist Should Know About Floating-Point
  Arithmetic***. Free, classic, and directly relevant.
- The **MuJoCo documentation's "Computation" chapter** — how the solver actually
  works, not just how to call it.
- Why: integrator error and stiffness are what make a simulation diverge. This
  harness detects four distinct divergence classes because ignoring them
  silently corrupted results. See `rigid-body-dynamics`.

---

# GATE 1 — Electronics + C

*120–200 hours. Unchanged from your version except where noted.*

## Electricity fundamentals
Ohm's law, voltage dividers, RC time constants, current limits.

- **Khan Academy — Electrical Engineering** (do the circuit analysis unit) → https://www.khanacademy.org/science/electrical-engineering
- **All About Circuits — Textbook, Vol I DC** → https://www.allaboutcircuits.com/textbook/direct-current/
- **Falstad Circuit Simulator** (draw a circuit, watch current flow) → https://www.falstad.com/circuit/
- **Book:** *Make: Electronics* by Charles Platt — experiments 1 through 11

## Components: transistors, MOSFETs, capacitors
- **Ben Eater — "What is a transistor?"** and the breadboard series → https://www.youtube.com/@BenEater
- **Ben Eater's site** → https://eater.net/
- **GreatScott! — Electronics Basics playlist** → https://www.youtube.com/@greatscottlab
- **SparkFun Tutorials** → https://learn.sparkfun.com/tutorials
- **Decoupling capacitors — why your servo browns out your MCU** → https://learn.sparkfun.com/tutorials/capacitors

## Reading a datasheet
- **ESP32-S3 Technical Reference Manual** (read the GPIO chapter) → https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf
- **ESP32-S3 Datasheet** (absolute max ratings, pinout) → https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf
- **Phil's Lab — "How to Read a Datasheet"** → https://www.youtube.com/@PhilsLab

## C programming
- **Book:** *The C Programming Language* — Kernighan & Ritchie. Do the exercises.
  **This is 60–100 hours on its own.** Budget it honestly or pick a subset.
- **Beej's Guide to C Programming** → https://beej.us/guide/bgc/
- **Exercism — C track** → https://exercism.org/tracks/c
- **Learn-C.org** → https://www.learn-c.org/
- **Bit manipulation practice** → https://graphics.stanford.edu/~seander/bithacks.html

## ESP32 firmware
- **ESP-IDF Programming Guide** → https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/index.html
- **ESP-IDF example projects** (read, don't copy) → https://github.com/espressif/esp-idf/tree/master/examples
- **Random Nerd Tutorials — ESP32** → https://randomnerdtutorials.com/projects-esp32/
- **DroneBot Workshop** → https://www.youtube.com/@Dronebotworkshop
- **Andreas Spiess** → https://www.youtube.com/@AndreasSpiess

## Debugging hardware
- **Sigrok / PulseView** → https://sigrok.org/wiki/PulseView
- **EEVblog — Multimeter and scope tutorials** → https://www.youtube.com/@EEVblog
- **big clive** → https://www.youtube.com/@bigclivedotcom

---

# GATE 2 — Control

*80–140 hours.*

## PID and closed-loop control
- **Brian Douglas — Control System Lectures** (start here) → https://www.youtube.com/@BrianBDouglas
- **Steve Brunton — Control Bootcamp** → https://www.youtube.com/@Eigensteve
- **Brett Beauregard — "Improving the Beginner's PID"** → http://brettbeauregard.com/blog/2011/04/improving-the-beginners-pid-introduction/
- **PID Without a PhD** (Tim Wescott, free PDF) → https://www.wescottdesign.com/articles/pid/pidWithoutAPhD.pdf

**Added — sampling and discrete time.** A controller runs at a fixed rate, and
that rate sets a hard limit on what it can respond to. Learn what the Nyquist
limit means before Gate 4, because a policy that "fails" on a sharp impact may
simply be running too slowly for any controller to have helped — a different
finding from "the policy is bad." Faultline runs at 50 Hz over a 2 ms physics
step; see the `control-theory` skill for what that costs.

## Encoders, timing, interrupts
- **Quadrature encoder basics** → https://www.dynapar.com/technology/encoder_basics/quadrature_encoder/
- **Nick Gammon — Interrupts (Arduino)** → https://www.gammon.com.au/interrupts
- **ESP-IDF — Timers and Interrupt Allocation** → https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/intr_alloc.html

## I2C and SPI at wire level
- **SparkFun — I2C** → https://learn.sparkfun.com/tutorials/i2c
- **SparkFun — SPI** → https://learn.sparkfun.com/tutorials/serial-peripheral-interface-spi
- Then capture both on PulseView and decode the bytes by hand once.

## IMU and sensor fusion
- **Complementary filter explained (Pieter-Jan)** → http://www.pieter-jan.com/node/11
- **MPU-6050 register map** (read it, don't just use a library) → https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf

## Robotics maths — the real thing
- **Modern Robotics — free preprint PDF + course materials** → http://hades.mech.northwestern.edu/index.php/Modern_Robotics
- **Book site** → http://modernrobotics.org
- **Coursera specialization (Northwestern, audit free)** → https://www.coursera.org/specializations/modernrobotics
- Chapters 1–3 at this gate: configuration space, rigid-body motions, forward
  kinematics.
- **Added — chapter 8, *Dynamics of Open Chains*.** Chapters 1–3 tell you where
  the robot is. Chapter 8 tells you what happens when forces act on it, which is
  what a simulator computes and what every perturbation axis manipulates. Do not
  reach Gate 3 without it.
- **3Blue1Brown — Essence of Linear Algebra** → https://www.3blue1brown.com/topics/linear-algebra

---

# GATE 3 — Simulation + RL

*150–250 hours. The gate that unlocks co-engineering Faultline.*

## Python and PyTorch, properly
- **Karpathy — Neural Networks: Zero to Hero** (build backprop by hand) → https://karpathy.ai/zero-to-hero.html
- **PyTorch official tutorials** → https://pytorch.org/tutorials/
- **Exercism — Python track** → https://exercism.org/tracks/python

## RL fundamentals
- **OpenAI Spinning Up in Deep RL** → https://spinningup.openai.com/en/latest/
- **Spinning Up — "Intro to RL"** (start exactly here) → https://spinningup.openai.com/en/latest/spinningup/rl_intro.html
- **Hugging Face Deep RL Course** (project-based; expect gym/gymnasium version friction) → https://huggingface.co/learn/deep-rl-course/unit0/introduction
- **Sutton & Barto — free official PDF** → http://incompleteideas.net/book/the-book-2nd.html
  - Chapters **3** (MDPs), **6** (temporal-difference learning), **9–10**
    (*added* — on-policy prediction and control with function approximation),
    **13** (policy gradients).
  - **Why 9–10 matter:** chapters 3 and 6 are *tabular* — one entry per state,
    which only works when states are countable. A robot's state is continuous,
    so there is no table. Chapters 9–10 are where a function replaces the table
    and where the word "deep" in deep RL actually enters. Skipping them means
    PPO arrives as magic.
- **David Silver — DeepMind RL lecture series** → https://www.davidsilver.uk/teaching/

## RL libraries
- **Gymnasium docs** → https://gymnasium.farama.org/
- **Stable-Baselines3** (after you have hand-written REINFORCE, not before) → https://stable-baselines3.readthedocs.io/
- **CleanRL** (single-file implementations — read PPO line by line) → https://github.com/vwxyzjn/cleanrl

## MuJoCo and simulation
- **MuJoCo documentation** → https://mujoco.readthedocs.io/
- **MJCF model format reference** (you will build the Bittle model in this) → https://mujoco.readthedocs.io/en/stable/XMLreference.html
- **MuJoCo Playground** (GPU-accelerated, runs on Apple Silicon) → https://playground.mujoco.org/ *(confirmed correct)*
- **MuJoCo Playground repo + notebooks** → https://github.com/google-deepmind/mujoco_playground
- **MuJoCo Playground paper** → https://arxiv.org/abs/2502.08844
- **Added — the "Computation" chapter of the MuJoCo docs.** How the solver works
  rather than how to call it: soft contacts, `solref`/`solimp`, integrator
  choice. This is what separates someone who runs a simulator from someone who
  can say why its output is wrong.

## Contact and dynamics — added
The single largest source of sim-to-real error, and the least taught.

- **Modern Robotics ch 11** (*Robot Control*) and **ch 12** (*Grasping and
  Manipulation*) — friction cones and contact modelling.
- **Featherstone — *Rigid Body Dynamics Algorithms***. The reference for how
  physics engines are actually built. Hard; treat it as a reference you dip
  into, not a book you read front to back.
- Why here: friction in MuJoCo has three components (sliding, torsional,
  rolling) and Coulomb friction is itself a simplification. Understanding what
  the model leaves out is the whole basis of Faultline's honesty about the
  sim-to-real gap.

## Evaluation — added, and it is your own subject
Everything else in this gate teaches you to *make* a policy. Nothing taught you
to judge one, which is the thing you are building a company around.

- **`docs/primer.md`** in this repo. Read it before Gate 4, not after.
- **Henderson et al. — *Deep Reinforcement Learning that Matters***
  (arXiv:1709.06560). Shows the same algorithm on the same task producing wildly
  different results across random seeds. This is why Faultline separates three
  seeds and why any single-run claim is worthless.
- **Badithela et al. — *Reliable and Scalable Robot Policy Evaluation with
  Imperfect Simulators*** — SureSim, https://arxiv.org/abs/2510.04354. The
  method behind the calibration layer in `docs/strategy.md`.
- The `uncertainty-and-evidence` skill in `.claude/skills/` — the claims ladder,
  and what N runs do and do not license you to say.

## Robot learning
- **Hugging Face Robotics Course** → https://huggingface.co/learn/robotics-course/en/unit0/1
  *(corrected: canonical path includes `/en/`, and it starts at unit 0)*
- **LeRobot documentation** → https://huggingface.co/docs/lerobot
- **LeRobot repo** → https://github.com/huggingface/lerobot

---

# GATE 4 — Sim to real

*120–400+ hours. Budget generously; this is the gate that breaks plans.*

## Read this before starting

Your Bittle's servos are **position-controlled hobby servos**. They give no
torque feedback, they have real backlash, and an MJCF model you write by hand
will capture neither. Add the quantisation any real control loop imposes and
the gap between your simulation and your robot is large and mostly invisible
from inside the simulation.

So: **expect the first transfer to fail, and expect the reason not to be
visible in simulation.** That is not a sign you did Gate 3 badly. RL locomotion
transfer onto low-cost position-controlled hardware is a research-grade problem,
not an exercise.

It is also the single most valuable thing that could happen to you. That gap —
measured, on your own robot, with your own hands — *is* the thing Faultline
exists to quantify. Write down what you expected, what happened, and what you
measured. That record is worth more to the company than a working gait.

## Sim-to-real transfer
- **Domain Randomization (Tobin et al.)** → https://arxiv.org/abs/1703.06907
- **Sim-to-Real: Learning Agile Locomotion for Quadruped Robots (Tan et al.)** → https://arxiv.org/abs/1804.10332
- **DreamWaQ — robust quadruped locomotion via implicit terrain imagination** → https://arxiv.org/abs/2301.10602
- **Lilian Weng — "Domain Randomization for Sim2Real Transfer"** → https://lilianweng.github.io/posts/2019-05-05-domain-randomization/

**Note the distinction** you will need constantly: domain randomisation is
*training-time* — the policy sees the variation and adapts. Faultline's
perturbation axes are *test-time* — the policy is frozen and we are finding
where it breaks. Failures found inside a customer's randomisation range mean
their training did not achieve what it intended; failures outside it are a
different claim. See `rl-for-robot-policies`.

## Deployment on hardware
- **ONNX Runtime docs** → https://onnxruntime.ai/docs/
- **Petoi OpenCat firmware repo** (your Bittle's actual code — read it) → https://github.com/PetoiCamp/OpenCat
- **Petoi documentation** → https://docs.petoi.com/
- **Nikodem Bartnik — SO-101 full build to trained policy** → https://www.youtube.com/@NikodemBartnik

## ROS 2
Pick **Jazzy** (battle-tested) or **Lyrical Luth** (May 2026 LTS, Ubuntu 26.04,
supported to 2031). Do not distro-hop. *(Verified: Lyrical Luth is real, May
2026, LTS through 2031.)*

- **ROS 2 Jazzy docs + tutorials** → https://docs.ros.org/en/jazzy/index.html
- **ROS 2 tutorials — start here** → https://docs.ros.org/en/jazzy/Tutorials.html
- **Articulated Robotics** (best free ROS 2 video series) → https://articulatedrobotics.xyz/
- **ROS 2 release schedule / distro policy** → https://docs.ros.org/en/rolling/Releases.html

*Note: Faultline does not use ROS. This gate is for the Bittle and for talking
to robotics teams, not for the harness.*

## Writing it up
- **How to write a research paper (Simon Peyton Jones)** → https://www.microsoft.com/en-us/research/academic-program/write-great-research-paper/
- **arXiv robotics (cs.RO)** — read 2 papers a week, skim 10 → https://arxiv.org/list/cs.RO/recent
- **Papers With Code — Robotics** → https://paperswithcode.com/area/robotics

---

# GATE 5 — Business (short on purpose)

- **The Mom Test** — Rob Fitzpatrick. ~130 pages. → https://www.momtestbook.com/
- **YC Startup Library** (only the "talking to users" essays) → https://www.ycombinator.com/library
- **Paul Graham — "Do Things That Don't Scale"** → https://paulgraham.com/ds.html
- Stop there. Your gap is not knowledge.

**One addition, and it is not reading.** `docs/roadmap.md` gates the backend on
someone who is not you running a campaign on their own robot. That does not
require any of Gates 1–4. It is worth doing *during* the study, not after —
finding out whether anyone wants this is the one thing no amount of learning
substitutes for.

---

# Communities — where to ask when stuck

| Community | Best for | Link |
|---|---|---|
| ROS Discourse | Serious robotics, high signal | https://discourse.ros.org/ |
| LeRobot Discord | Robot learning, current, active | https://huggingface.co/docs/lerobot |
| Electronics Stack Exchange | Circuit questions | https://electronics.stackexchange.com/ |
| r/embedded | Firmware. Harsh but correct. Read sidebar first. | https://reddit.com/r/embedded |
| EEVblog Forum | Deep hardware expertise, low patience | https://www.eevblog.com/forum/ |
| Petoi Forum | Bittle-specific | https://www.petoi.camp/forum |
| r/reinforcementlearning | RL direction and papers | https://reddit.com/r/reinforcementlearning |
| Hackaday.io | Publish your builds, get feedback | https://hackaday.io/ |
| FOSDEM robotics + embedded devrooms | Free recorded talks | https://fosdem.org/ |

**Asking format that gets answers:** what you're trying to do → what you
expected → what happened → what you measured → what you already tried. Attach
the scope trace.

---

# Reference lists worth bookmarking

- **Embedded Engineering Roadmap** → https://github.com/m3y54m/embedded-engineering-roadmap
- **Awesome Robotics** → https://github.com/kiloreux/awesome-robotics
- **Awesome Robotics Libraries** → https://github.com/jslee02/awesome-robotics-libraries

---

## Order of operations

**Path A — Faultline first (5–6 months to co-engineering):**
Python + PPO + MuJoCo → PID + encoders + IMU → sim-to-real on Bittle →
C + circuits → your own opinion about what's broken.

**Path B — Robotics first (your original, 10–12 months):**
C + circuits → PID + encoders + IMU → MuJoCo + PPO → sim-to-real on Bittle →
ROS 2 → your own opinion about what's broken.

The maths track runs alongside either, throughout.
