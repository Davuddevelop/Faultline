# Teeter

The website under the company's new name, and the identity standard it is
built from. The software and its command-line tool keep the working name
`faultline` until they are renamed.

| Path | What |
| --- | --- |
| `index.html` | the site, sections TT-101 to TT-109; the builder also writes it to the repository root as the front page |
| `app/` | the product (TT-301 to TT-360), every screen in `docs/product-plan.md`: live against the API when it serves the page (`app/js/live.js`), the prototype anywhere else |
| `brand/index.html` | the identity standard, eleven sheets TT-000 to TT-010 |
| `brand/*.svg`, `brand/geometry.json` | the mark, wordmark, lockups and favicon, and the numbers they are drawn from |
| `css/`, `js/`, `assets/fonts/` | styles, the motion script, the 3D replay (`js/machine.js`, shared with `app/`), Archivo and B612 Mono (SIL OFL), self-hosted |
| `assets/og.png` | the 1200 × 630 social card |
| `vendor/` | three.js and GSAP, self-hosted; see `vendor/README.md` |

Nothing here is drawn by eye or typed by hand:

| Figure or value | From |
| --- | --- |
| The gyroscope symbol, the stencil wordmark, every logo file | `tools/build_brand.py`, pure geometry |
| The 3D replay in the opening: torso pose, leg bodies and feet per control step | `media/sim.json`, captured by `media/capture_sim.py` |
| Measured tilt, nominal against the smallest failing push | `media/sim.json`, captured by `media/capture_sim.py` |
| Where the budget went, sample efficiency, coverage, reduction, failure modes | `assets/data/campaign.json` |
| The uniform rate and its 95% Wilson interval | `assets/data/campaign.json`, the random arm only |
| The config sample in TT-103 | the record's axes, rules, budget and reduction; the rest is what `faultline init` writes, and the page says so |

## Rebuilding

```sh
python3 tools/build_brand.py              # logo files and the identity standard
python3 tools/build_teeter_site.py        # the site's figures and values
python3 tools/build_teeter_app.py         # the app prototype's record data
python3 tools/build_teeter_site.py --og   # also the social card (Playwright)
python3 tools/fetch_fonts.py teeter       # only if the faces change
```

`build_teeter_site.py` stops if the breach time recomputed from the captured
physics disagrees with the record. `harness/tests/test_teeter_site.py` fails if
the page goes stale, if its config sample stops loading, or if its axis table or
signal list drifts from the harness.

## The app prototype

`app/` runs two ways.

**Served by the control plane** (`teeter-api serve`, see `api/README.md`),
`app/js/live.js` finds `/v1/health` and the app runs against the API: sign-in
by link, campaigns planned, streamed, reduced and replayed, runners, programs
and gates, all from the workspace's own database. Every live panel carries a
**live** tag. Screens that are not built yet (evidence, spaces and rules,
integrations, first-day setup) stay the prototype's, under a strip that says
they show example data.

**Anywhere else** (the static site), no API answers and it is a clickable design
of the product, not the product: nothing is connected. Every panel carries a
tag. **record** panels are drawn from `app/js/record.js`, which
`tools/build_teeter_app.py` writes from the campaign record and the harness
source; `harness/tests/test_teeter_app.py` fails if it drifts from the harness.
**example** panels come from `app/js/example.js`, which is illustrative
throughout: the workspace, Q2, its checkpoints and gates, the runners, people
and keys do not exist. Record content only appears under the record's own names
(C-0001, EP-0001), never under an example's.

## Placeholders

`hello@teeter.dev` is **invented**. No mailbox exists and teeter.dev is not
registered to us; the page says so beside the address. `og:image` is a relative
path and needs an absolute URL once the site has a domain.
