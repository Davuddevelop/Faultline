# Faultline

Landing page for Faultline — adversarial testing for learned robot policies.

Static HTML and CSS. No build step, no framework, no external requests at
runtime: fonts are self-hosted and every image is local.

```
python3 -m http.server 8000     # then open http://localhost:8000
```

## The page

`index.html` is the site. Imagery carries the hero, one mid-page plate and the
contact screen; everything between them is a spec sheet.

| Section | What it does |
| --- | --- |
| Hero | The fissure image, full bleed, headline sitting in it |
| The problem | Why a passing test suite proves less than it looks like it does |
| Why now | Regulation (EU) 2023/1230 and the 20 January 2027 date |
| How a run works | Five stages: ingest, perturb, search, detect, reduce — with the campaign config that drives them |
| The search space | A real table of perturbation axes, units and illustrative ranges |
| What counts as a failure | The violation predicates, plus a schematic trace of one being crossed |
| Hardware validation | Full-bleed plate, stating plainly that this is in progress |
| Deliverables | The two documents and the run archive, with contents |
| Interfaces | Simulators, model formats, policy formats, outputs |
| To start | The three inputs needed from a customer |
| Where this stands | What can be shown and what cannot |
| Contact | One call to action |

### Why it reads this way

The middle of the page is deliberately not atmospheric. For a company selling
safety evidence, credibility comes from showing the machinery — the axes it
searches, the predicates it checks, what lands in the report — not from
adjectives about it. The photography sets the tone at the top and bottom; the
part that has to be believed is a table.

Nothing on the page claims a result. Ranges are labelled illustrative,
predicates are labelled as supported forms, and the hardware plate says
outright that there is nothing to show yet.

## The sample report

`report/` publishes a real campaign: failure modes, sample efficiency and
coverage from 150 simulations against the stand-in quadruped. The deliverables
section of the landing page links to it, so the page shows its output rather
than only describing it.

The page is **generated, not hand-written** — edit the generator, never
`report/index.html`:

```bash
cd harness && python3 examples/report_one.py   # produce a fresh campaign
python3 tools/build_report_page.py             # rebuild the page from it
```

It reads `assets/data/campaign.json`, so every number on the page is a number
the harness printed.

### The chart colours are not the brand colours

The site's `--sage` and `--glacial` **fail** as a two-series pair: normal-vision
ΔE 9.8, below the 15 floor, meaning full-colour readers cannot reliably tell
the two series apart. The charts use `#2BA476` and `#6E89DC`, which pass all six
checks of the dataviz validator against both the panel and page surfaces
(normal ΔE 20.3, deutan 16.2). The reason is recorded at the top of
`report/report.css` so it does not get "corrected" back.

Series labels are direct-labelled in ink with a small coloured rule beside
them, rather than coloured text, so identity survives colour-vision deficiency.

## Design exploration

`v1/`, `v2/` and `v3/` are the three directions built before this one; the
page above is `v3` carried through. `archive/scene/` is an earlier version
whose hero was a drawn SVG landscape rather than photography — no imagery at
all, kept because it still stands on its own.

## Images

`assets/img/` holds three sources, each as WebP at 800 / 1280 / 2048 with a
JPEG fallback, served through `<picture>` with `srcset`:

- `fissure` — a robot at the edge of a break in the ground
- `moss-walk` — a quadruped crossing a mossy ridge in fog
- `valley-line` — robots walking a line across a wide valley

`manifest.json` records each image's dominant colour, painted behind it so
there is no flash before it loads. The directory is ~1.5 MB in total.

## Type and colour

Instrument Serif appears **only in the hero**, where it is doing brand work.
Every section heading below it is IBM Plex Sans — the display serif running
the length of the page is what made early drafts read like a research lab
rather than a company that ships hardware. IBM Plex Mono carries every
number, label, unit, predicate and config key. Self-hosted in
`assets/fonts/`.

Deep forest ground with a single **glacial blue** accent lifted from the sky
in the illustration. It marks the italic word in the headline, the date, the
range column, the predicate rules and the one call to action — and nothing
else. `v1` runs a chalk-and-pine variant of the same idea. `v2` and
`archive/scene/` still carry the original amber from the content spec.

## Before this goes live

- **The call to action points at `mailto:hello@faultline.dev`, a placeholder.**
- Verify both paragraphs of the "Why now" section against EUR-Lex. If a
  notified body engineer corrects any of it, fix the page that day.
- The illustrative ranges in the search-space table, and the values in
  `campaign.yaml`, are defaults for a mid-size quadruped. Replace them with
  real ones before showing this to anyone who builds robots.
- The trajectory trace is a schematic and says so. Swap it for a real run as
  soon as you have one — a measured trace is worth more than everything else
  on the page.
- **The two illustrations are generated art.** The moss-walk photograph is the
  only real image here, and it is the one that reads as a robotics company.
  Replace the illustrations with footage of your own hardware when you have
  it.
- Keep "Where this stands". For a safety-evidence product, saying plainly what
  you cannot yet show is the strongest trust signal on the page.

## Verified

Every page, at 1440 / 768 / 390 and under `prefers-reduced-motion`: no console
errors, no failed requests, no horizontal overflow, every image loading with
alt text, and every reveal firing under normal scrolling.
