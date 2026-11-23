# Teeter — the next six months

*Written 15 October 2026, for 16 October 2026 to the end of March 2027.
Builds on `docs/founder-brief.md` (what gates the company), `docs/roadmap.md`
and `docs/v1-roadmap.md` (what to build). Durations are estimates for one
person in school, working with AI help, not promises.*

---

## The one idea behind the order

The engine works and is better than it needs to be at this stage. Nobody
outside this repository has ever run it. The scarce thing is not code; it is
contact with people who ship learned robot policies. So for the next six
months **talking leads and building follows**. Each month builds only what the
last month's conversations asked for.

One date shapes everything: the EU Machinery Regulation 2023/1230 applies from
**20 January 2027**. The delegated act that says what adequate evidence is
will not come before 2028. Teams therefore have to decide what to show without
a rule to follow, and that gives them a reason to take a call now.

**Time.** School comes first. This plan assumes about **12 hours a week** in
term time and more in holidays. Pick your own number and keep it fixed. A
plan that needs more than you have is a plan to burn out.

---

## Phase 0 — Be reachable and protected (16 Oct – 1 Nov)

Small jobs that become urgent exactly when something good happens.

1. **A real address.** `hello@teeter.dev` is invented, and `teeter.dev` is not
   registered to us. Right now nobody who reads the site can reach you.
   Register a domain you control and set up the mailbox. The address then has
   to change in one pass everywhere it appears, which Claude can do:
   - the site (`teeter/index.html`, then `tools/build_teeter_site.py`);
   - the app's sign-in screen (`teeter/app/js/app.js`);
   - the brand book;
   - the test that checks it (`harness/tests/test_teeter_site.py`).

   *Done when* a message sent to the address on the live site reaches you.
2. **Name the adult.** Under 18 you cannot sign contracts, open a business
   account or register a company on your own. Agree now with a parent or
   guardian that they will co-sign when money or an agreement appears.
   *Done when* they have read `docs/founder-brief.md` §5 and said yes.
3. **Decide what is public.** The repository is public and has no licence.
   Choose either to keep the code public and add a licence, or to make it
   private. Then decide whether `docs/strategy.md` (prices, competitors)
   stays readable by anyone. Both are your calls; making either change takes
   minutes.
4. **One page on data.** Write the answers every engineer will ask before
   running anything: where their data lives, who sees it, what you keep
   afterwards, what happens if you stop. The short answer is the strongest one
   you have: *you run it on your machines and send us results, never weights*
   (`docs/founder-brief.md` §4).
5. **Write down the decision rules** in §6 below, before you care about the
   answer.

---

## Phase 1 — Ten conversations and a proof on someone else's robot (2 Nov – 20 Dec)

Two tracks in parallel. Talking takes about 4 hours a week, building about 6,
and learning about 2.

### Talking

1. **Build a list of 40 names**: people who train or ship learned locomotion
   policies. Look for authors of recent legged and humanoid locomotion papers,
   maintainers of open training code (MuJoCo Playground, Isaac Lab tasks),
   engineers at companies putting legged or humanoid robots on the EU market,
   and university legged-robotics labs. Keep it in one sheet: name, why them,
   date contacted, reply, next step.
2. **Send about 10 short messages a week.** Ask a question, not for a sale:
   *"How do you test a policy before it goes on hardware, and what would you
   want to be able to show before January 2027?"* Link
   `docs/walkthrough.md` or the site so the work speaks first. Expect most not
   to answer; that is normal for cold messages.
3. **Run each call the same way, in 20 minutes:**
   - How do they test a new checkpoint today?
   - What was the last surprise on hardware?
   - Who decides a policy is ready to ship?
   - What would they need to show a customer or an assessor?
   - Would they run a command on their own machine and send back the results
     archive?

   Write notes the same day. Never say safe, verified, validated, certified
   or compliant, in a call or in a follow-up.
4. **Your age.** Don't lead with it, and don't hide it if asked. The tool, the
   walkthrough and the published campaign are the introduction.

*Done when* 10 conversations have happened with people who ship learned
policies, each with written notes.

### Building: the public proof (`docs/roadmap.md` A6)

Everything published so far uses a robot and a policy we wrote. Run Teeter
end to end on **a public robot and a policy someone else trained**. For the
robot, a quadruped from MuJoCo Menagerie would do (a Unitree or ANYbotics
model, for example). For the policy, use one released openly. If none fits,
ask someone on your list for one; that is a natural first collaboration.
Training one yourself from an open recipe is the fallback, and it is weaker
evidence.

- Load the robot (URDF or MJCF, already supported in `model.py`) and the
  policy (ONNX or TorchScript, already supported in `adapters.py`), and map
  its observation layout (`observe.py`). Mapping the observation layout is
  where integrations usually fail, so expect to spend most of the time there.
- Run a campaign, reduce the failures, and publish the record the way the
  current one is published, generated by the tools and never written by hand.
- *Done when* the site shows a failure found in a policy you did not write.

### Money, small and without giving up equity

Once the proof is published and you have had a few conversations, apply for
a grant that takes no share of the company. Emergent Ventures, for example,
funds teenagers. Do not raise from investors in this period (§5).

---

## Phase 2 — The first design partner (21 Dec – 31 Jan)

1. **Pick one or two teams** from the conversations that will run the harness
   inside their own infrastructure and send back the archive
   (`report.json`, `manifest.jsonl`, traces). Their weights never leave their
   machines.
2. **Build only what they need**, usually from `docs/v1-roadmap.md` M2:
   - their observation layout;
   - a smoke test;
   - a quick start that works on a laptop without a GPU.

   If they train in Isaac rather than MuJoCo, that is the biggest risk in the
   plan. Say so early and decide together whether to wait for M6.
3. **A weekly 20-minute check-in** with each partner.
4. **20 January 2027**, the day the regulation applies, is a natural moment to
   publish a short, plain note: what the regulation asks, what a campaign
   shows, and what it cannot show. It cannot show that a policy is safe,
   because the harness finds failures and cannot prove their absence.

*Done when* someone who is not you has run a campaign on their own robot.

---

## The 90-day check (about 15 January)

Taken from `docs/founder-brief.md` §8, with dates.

**Continue** if, by mid-January:
- at least two teams that ship learned policies have taken a real call;
- at least one has run the harness on their own robot;
- you have found at least one failure mode in something you did not write.

**Change the wedge** if teams keep saying regression testing is solved in
house and evidence is what they lack. The business is then the evidence layer
alone: slower, more regulatory, and it needs an EU entity.

**Stop or pause** if two serious rounds of outreach get no conversations at
all.

**Not a reason to stop:** slow progress, no revenue, or a competitor
announcing something nearby. All three are expected.

---

## Phase 3 — Deepen what worked (February – March)

Only if the check says continue.

1. **Make the partner's use routine.** Run the gate in their CI
   (`docs/v1-roadmap.md` M3) and diff checkpoint against checkpoint, so Teeter
   runs on every policy change and not once.
2. **Put the hosted control plane online** (`docs/decisions.md`, about an hour
   of your clicks), but only if a partner wants it rather than running
   locally.
3. **One advisor.** Ask the most technical person you have spoken to for a
   30-minute call once a month to check the method. It stays informal until
   there is a company.
4. **Look for a co-founder among people you have worked with**, not people you
   have only met. Work on a real task together for a month or two first. Any
   co-founder's shares vest over four years with a one-year cliff.
5. **Prepare the entity with your parent or guardian**, but don't form it until
   a customer or a grant needs one. `docs/founder-brief.md` §5 lists what to
   research, including the EU-entity question.

*Done when* one team uses Teeter on more than one checkpoint, and you can name
the failure modes it found that they did not know about.

---

## The week, in practice

| When | What | Hours |
| --- | --- | --- |
| One weekday evening | Outreach: messages, follow-ups, updating the sheet | 1–2 |
| Two weekday evenings | Building | 3 |
| Weekend | Building, then calls when they are booked | 4–5 |
| Weekend | Learning, in the order of `docs/founder-brief.md` §10: control and simulation fidelity, then statistics and evidence, then contact dynamics, then RL | 2 |
| Sunday, 30 minutes | Review: the counts below, and next week's three goals | 0.5 |

Count only these (`docs/founder-brief.md` §9):
- conversations with people who ship learned policies;
- campaigns run by someone who is not you;
- failure modes found in a policy you did not write;
- failures reproduced on hardware;
- numbers on the site that cannot be traced to a file (target zero).

---

## What we do not do in these six months

| Not doing | Why |
| --- | --- |
| Raise from investors, or make a pitch deck | Nothing yet shows the product is wanted. With a proof and a partner you will raise on better terms and keep more control. |
| Form a company | Nothing needs one until money or a contract appears |
| Redesign the site again | It is good enough. Change it only when a conversation shows it confuses people. |
| Support Isaac, manipulation or hardware | Only when a partner needs it (`docs/v1-roadmap.md` M6) |
| Claim the output is safe, verified, certified or compliant | It never can be, and saying it creates liability |

---

## Where Claude helps, and where it can't

**Claude can:** build what each phase needs, draft messages and call
questions, prepare you for a technical call, turn your call notes into the next
week's goals, and keep every number on the site traceable to a file.

**Only you can:**
- have the conversations;
- decide what the product may claim;
- understand the physics well enough to defend a result to an engineer with
  fifteen years on real robots;
- decide what not to build.
