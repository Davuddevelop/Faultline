# Learning to build this, from the start

*6 October 2026. Written for someone who has not written Python yet. Every term
is explained the first time it appears. If a sentence here needs other
knowledge to understand, it is a mistake — tell me and I will fix it.*

There are two other files about learning. Read them later, not now:

- `docs/build-syllabus.md` — the same subject, written for someone who already
  codes. Come back to it at Stage 5.
- `docs/founder-syllabus.md` — what to know to *talk* about the harness. Useful
  from day one, but it is a different job from building.

---

## What this is for

Right now the harness in `harness/` is about 4,900 lines of Python. I wrote
almost all of it — 40 of the 41 commits in this repository are mine. That is
fine for getting started and it is not fine as a permanent arrangement, because
a founder who cannot read their own product cannot defend it, fix it, or decide
what it should become.

**The goal of this plan: you can open any file in `harness/`, understand what it
does, and change it without breaking it.**

That is the finish line. Everything below is the road to it.

## How long this honestly takes

At **8–10 hours a week**, roughly **7 to 9 months** to reach that finish line.

Not three weeks. Not "a weekend of tutorials". Anyone who tells you otherwise is
selling something. The upside is that the clock is on your side: the regulation
that matters applies in January 2027 and the standard defining adequate evidence
is not due until 2028, so you are not racing anyone to a deadline next month.

At 3–4 hours a week it is closer to 18 months. That is still a real path. It is
just a slower one, and worth knowing before you start rather than after.

## The one rule about how to study

**Write code every session. Do not watch videos without writing code.**

Watching someone program feels like learning and is not. The feeling of
understanding while you watch disappears the moment you face an empty file. The
only thing that works is typing code, getting errors, and fixing them.

A good session: 20 minutes reading or watching, 60 minutes writing.
A bad session: 90 minutes watching.

---

# Stage 0 — Run the thing. One evening.

Before learning anything, make the harness run on your own computer. You will
not understand what you are running. That is fine. The point is that it stops
being an abstraction.

1. Install Python from python.org — version 3.11 or newer.
2. Install a code editor: VS Code is free and standard.
3. Open a terminal in the `Faultline` folder and type these, one line at a time:

```sh
cd harness
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m pytest tests/ -q
faultline init my-campaign.yaml
faultline run my-campaign.yaml
```

4. Look at the files it produced: `engineering-report.md`,
   `safety-appendix.md`, and the `archive/` folder.

**Done when:** you have run a campaign on your own machine and read the report
it produced.

**What to expect:** I ran exactly these commands on 6 October 2026. The tests
take about 100 seconds and end with `164 passed, 4 skipped`. The campaign is 120
simulations and takes about 13 seconds; it finds 43 failures, reduces them to 3
distinct modes, and writes everything into a `deliverables/` folder. If your
numbers differ, something is different about your machine and that is worth
knowing early.

**If it fails:** that is normal and the error message is the lesson. Paste it to
me. Working out why a thing will not install is a real skill and you will use it
constantly.

> A note on the first two lines: `venv` makes a private box for this project's
> installed packages so they do not collide with anything else on your computer.
> `pip install -e ".[dev]"` installs the harness plus the testing tools. You do
> not need to understand that yet.

---

# Stage 1 — The Python language

**8 weeks. The foundation. Do not skip it and do not rush it.**

Use **one** main resource, not five. Pick either:

- *Automate the Boring Stuff with Python* by Al Sweigart — free to read online,
  aimed exactly at beginners, chapters 1–6 then 8–9.
- *Python Crash Course* by Eric Matthes — a paid book, slightly more structured.

Alongside it, do exercises on **Exercism**'s Python track. Free, and it gives
you small problems with feedback rather than blank pages.

*(Links are deliberately not pasted here — search the titles. The link list in
`docs/learning-path.md` was checked in August and these have not been.)*

### Week by week

| Week | What | You can do this at the end |
| --- | --- | --- |
| 1 | Variables, numbers, text, `print`, `input` | Write a program that asks for a number and prints whether it is even |
| 2 | `if` / `else`, comparisons, `and` / `or` | Write a program that grades a score into A–F |
| 3 | Loops: `for` and `while` | Print the first 50 numbers where the number is divisible by 7 |
| 4 | Lists and dictionaries | Store ten test results and print the worst three |
| 5 | Functions — your own, with arguments and return values | Rewrite week 4 so each piece is a named function |
| 6 | Reading and writing files | Read a list of numbers from a file, write the average to another file |
| 7 | Errors: what a traceback says, `try` / `except` | Make week 6 survive a missing file and say so clearly |
| 8 | **Build something of your own, ~150 lines** | A small program that does something you actually want |

### Week 8 matters more than weeks 1–7

Pick something real. A script that renames your files. Something that reads a
CSV and prints a summary. It does not matter what — it matters that nobody gave
you the steps.

**Done when:** you can open an empty file and write a 100-line program that
works, without a tutorial open beside you.

---

# Stage 2 — Python for real programs

**6 weeks. This is the gap between "I can write a script" and "I can work in a
codebase".**

Everything here appears in `harness/` on almost every page, which is exactly why
that other syllabus was unreadable.

### Week by week

| Week | What | Why it is in your codebase |
| --- | --- | --- |
| 1 | **Classes** — bundling data and behaviour together | `Trajectory`, `RunSpec`, `Report` are all classes |
| 2 | **Dataclasses** — a shorter way to write classes that mostly hold data | Nearly every class in `harness/` is one. `spec.py` is almost nothing else |
| 3 | **Type hints** — writing down what kind of thing a variable is | Every function in `harness/` has them. They are how you read code without running it |
| 4 | **Modules and imports** — splitting code across files | `harness/faultline/` is 15 files that import each other |
| 5 | **pip, venv, pyproject.toml** — installing and packaging | You used these in Stage 0 without knowing it |
| 6 | **pytest** — automated tests | There are 168 in `harness/tests/`; 164 pass and 4 skip. They are the only reason anyone can trust the thing |

### Also learn, in parallel: git

Not a week — an hour, then use it daily. `git add`, `git commit`, `git push`,
`git log`, `git diff`. Read the first three chapters of *Pro Git* (free online).

You will touch this every single day for the rest of the project. Learn it
early and badly rather than late and well.

### The exercise that proves Stage 2

Open `harness/faultline/spec.py`. It is 141 lines and it is the simplest
important file in the project.

Read it line by line. For every line, answer: *what does this do, and why is it
there?* Write your answers in a file. Bring me the ones you cannot answer.

**Done when:** you understand all 141 lines of `spec.py`.

---

# Stage 3 — NumPy and the maths you actually need

**4 weeks.**

### NumPy

NumPy is a Python library for working with lists of numbers quickly. A
trajectory — the record of what the robot did, step by step — is stored as
NumPy arrays. You cannot read the harness without it.

Work through the official *NumPy: the absolute basics for beginners* guide,
then practise: make arrays, slice them, do arithmetic on whole arrays at once,
find the maximum, filter by a condition.

### The maths

Less than you fear. You need four things:

1. **Degrees and radians**, and converting between them. Python's trig
   functions want radians; your reports show degrees.
2. **Basic trigonometry** — `sin`, `cos`, and what they mean on a circle. The
   slope perturbation is built entirely from these.
3. **Vectors** — a list of three numbers that means a direction and a size.
   Gravity is one. A push is one.
4. **Matrices, just enough** — what multiplying a vector by a 3×3 matrix does
   (it rotates it), and what "transpose" means. Tilt is computed from one number
   inside a rotation matrix.

**Where:** Khan Academy for trigonometry and the start of linear algebra.
3Blue1Brown's *Essence of Linear Algebra* videos for intuition — this is the one
place where watching is genuinely worth it, because the subject is visual. Then
write the code.

**Done when:** you can write a function that takes an angle in degrees and
returns the gravity vector for a slope of that angle — and check it against
`_apply_perturbation` in `harness/faultline/runner.py`.

---

# Stage 4 — Simulation and MuJoCo

**8 weeks. The first part that is specific to your product.**

MuJoCo is the physics simulator the harness runs on. It is the thing that
actually computes what happens when a simulated robot is pushed.

### The one idea to get first

MuJoCo splits the world into two things:

- **the model** — what exists and does not change during a run: the robot's
  shape, masses, how heavy gravity is, how slippery the floor is
- **the data** — what is happening right now: where each part is, how fast it is
  moving, what force is being applied

Every perturbation in your harness changes **the model** before the run starts.
Then the run steps **the data** forward in time, thousands of times.

Once that split is clear, most of MuJoCo's documentation becomes readable.

### Week by week

| Weeks | What |
| --- | --- |
| 1–2 | MuJoCo's own documentation: the Overview and the MJCF model format. Load the quadruped in `harness/models/` and look at it |
| 3–4 | Write a script that loads the model, steps it 250 times, and prints how high the body is at each step |
| 5–6 | Add a push: apply a force to the body for a short window and watch it fall over |
| 7–8 | Compute tilt yourself — get the rotation matrix, take the right entry, convert to degrees |

### The exercise that proves Stage 4

Write that last script **without opening `runner.py`**. Then open `runner.py`
and compare. The differences are your remaining gaps, and they will be
specific enough to ask about.

**Done when:** your own script produces a tilt number that matches what the
harness produces for the same push.

---

# Stage 5 — Read your own harness

**4 weeks. One file at a time, in this order.** Each builds on the one before.

| Order | File | The question to answer |
| --- | --- | --- |
| 1 | `spec.py` | What exactly describes one test? (You did this in Stage 2 — reread it; it will look different now) |
| 2 | `space.py` | What is "the volume being searched", in code? |
| 3 | `predicates.py` | How does the code decide a run failed? |
| 4 | `model.py` | How is a robot file turned into something the runner can use? |
| 5 | `observe.py` | What numbers does the policy get handed, and in what order? |
| 6 | `runner.py` | **The heart of it.** How does one run actually happen? |
| 7 | `record.py` | What does a run leave behind, and how is it proved reproducible? |
| 8 | `reduce.py` | How is a failure walked back to its smallest form? |
| 9 | `search.py` | How does the program choose what to try next? |
| 10 | `report.py` | How do the deliverables get written? |

For each: read it, write a paragraph in your own words explaining what it does,
and list what you did not understand. Bring me the lists.

Now go and read `docs/build-syllabus.md`. It will make sense at this point, and
it covers the detail this file deliberately leaves out.

**Done when:** you can explain, out loud and without notes, what happens between
typing `faultline run` and the report appearing.

---

# Stage 6 — Change it

You are no longer learning. You are building. Four real jobs, easiest first.
Every one of them improves the product.

### 1. Add an eighth perturbation axis

There are seven today. Add one — wind, or a step in the floor, or whatever is
physically sensible. You will touch `reduce.py` (the list of axes), `runner.py`
(applying it), and the tests.

**Why first:** it is the smallest change that forces you through the whole
system.

### 2. Fix the impulse bug

A known defect. When the harness is asked for a push of 7.875 N·s, the robot
receives roughly 20% more than that, because the push is spread over 0.05
seconds but applied on a 0.02-second grid. Every number in every document says
"requested" because of this.

Fix it, and write the test that would have caught it.

**Why second:** it is a real defect with a real cause, and fixing it makes every
impulse number on the website truer than it is today.

### 3. Build the confidence-interval calculator

Given the number of runs and the number of failures, work out what can honestly
be claimed. Make it refuse when the runs were not uniformly sampled.

**Why third:** this is the first piece of the part of the product that is hardest
to copy.

### 4. Build `faultline diff`

Compare two versions of a policy and report what got worse. It does not exist
yet, and `docs/roadmap.md` calls it the wedge — the feature that gets a team to
use this every day rather than once a year.

**Why last:** the hard part is deciding what "the same failure" means, which
takes judgement rather than syntax.

---

# Things that will waste months

Each one is more appealing than what you should be doing.

| Do not, yet | Why |
| --- | --- |
| **Learn C first** | `docs/learning-path.md` starts with electronics and C. That is a fine path to becoming a roboticist and the wrong path to maintaining this product. Your product is Python |
| **Learn machine learning** | You test policies other people trained. The harness never trains anything |
| **Learn web development** | Your website is plain HTML files. There is no app to build |
| **Build a new feature before Stage 5** | You will write code you cannot maintain, and the repository is already too full of code you did not write |
| **Do more tutorials after Stage 1** | After about week 8, every extra tutorial is avoidance. Write your own programs instead |
| **Switch resources when it gets hard** | Finding a better course is the most comfortable way to not learn. Finish the one you started |

---

# When you get stuck

Stuck is the normal state of programming. It is not a sign you are bad at it.

1. **Read the error message.** Properly, all of it. The last line says what
   went wrong; the lines above say where.
2. **Make the smallest version that still fails.** Delete everything unrelated.
   Half the time the answer appears while you are deleting.
3. **Print things.** Put `print(...)` before the line that breaks and look at
   what the values actually are rather than what you assume they are.
4. **Ask me**, and paste the error, the code, and what you expected instead.
5. **Rule: thirty minutes.** If you are no further after thirty minutes, ask.
   Beyond that you are not learning, you are grinding.

---

# A weekly rhythm that works

- **Four sessions a week, 2 hours each.** Shorter and more often beats one long
  Saturday, because the forgetting happens in between.
- **Start each session by rereading the last thing you wrote.** Two minutes,
  and it restores the context you lost.
- **End each session mid-task**, not at a clean finish. Starting is harder than
  continuing, so leave yourself something to continue.
- **Commit every session**, however small. `git commit -m "week 3: loops"` is a
  real record of a real thing.
- **One line in a log file each week:** what you learned, what you did not.
  After six months it is the only honest account of your own progress you will
  have.

---

# Where you are

Copy this into a file and tick as you go.

```
[ ] Stage 0  ran a campaign on my own machine
[ ] Stage 1  can write a 100-line program from scratch        (8 weeks)
[ ] Stage 2  understand every line of spec.py                 (6 weeks)
[ ] Stage 3  can compute a slope gravity vector myself        (4 weeks)
[ ] Stage 4  my own script's tilt matches the harness         (8 weeks)
[ ] Stage 5  can explain a whole run, out loud, from memory   (4 weeks)
[ ] Stage 6  shipped a change to harness/ that I wrote
```

Seven lines. Thirty weeks. At the end of them, this is your product rather than
code someone handed you — and that difference is the whole reason to do it.
