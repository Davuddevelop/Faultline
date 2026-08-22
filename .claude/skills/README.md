# Skills

Project skills for this repo. Claude loads the `name` and `description` from
each `SKILL.md` at session start and reads the body only when a task matches,
so the standing cost is the descriptions (~1k tokens), not the content.

## Where these came from

| Source | Licence | Skills |
| --- | --- | --- |
| [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code) | MIT (see `LICENSE-everything-claude-code`) | 14 |
| [`anthropics/skills`](https://github.com/anthropics/skills) | see upstream | `frontend-design` |
| Written for this repo | — | `robot-policy-testing` |

ECC ships 286 skills. 14 are installed. The rest are for stacks this project
does not use (Laravel, Django, healthcare, DeFi, logistics) and installing them
would cost context on every turn and widen the surface of instructions Claude
follows for no return.

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

**Machines**
- `robot-policy-testing` — this project's domain conventions
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
