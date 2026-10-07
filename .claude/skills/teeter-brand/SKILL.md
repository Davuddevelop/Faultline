---
name: teeter-brand
description: Teeter's identity and voice — the tipping-block mark and its exact geometry, the graphite and vellum tone scale with no colour, failure shown only by hatching at 35°, Archivo and B612 Mono, ISO 128 drawing conventions, the generated-figure pipeline behind teeter/, and the copy rules. Use when designing, building or reviewing anything branded Teeter (the site in teeter/, the identity standard at teeter/brand/, a deck, a figure, a social card, a report cover) or when a page or document still says Faultline.
metadata:
  origin: written for this repo
---

# Teeter

**Teeter** is the company. The software and its command-line tool keep the
working name `faultline` until they are renamed, so `faultline run campaign.yaml`
is correct on a Teeter page. The previous identity (the name Faultline on the
site, the stacked-bars mark, Newsreader and Geist, the oxide accent) is
withdrawn; the root `index.html` and `ink/` still carry it.

The register is an **engineering drawing**: sheets with zones, numbered
drawings, title blocks, dimension lines, line types after ISO 128. Not a
startup landing page. The full standard is eleven sheets at
`teeter/brand/index.html` (TT-000 to TT-010); this file is the working summary.

## The mark

A block 7 modules wide and 10 tall, balanced on its corner P at
θc = arctan(7/10) = **34.992°**. At that angle the diagonal PT is vertical and
the centre of mass G sits directly over P: any further and it falls. The
published campaign's failure rule is `tilt_deg > 35.0`, so the mark is a
picture of the condition the product looks for. Say exactly that; do not claim
the two angles are the same physical quantity.

Corners, in modules, P at the origin (`teeter/brand/geometry.json`):

| Point | x | y |
| --- | --- | --- |
| P, pivot | 0 | 0 |
| left | −5.734623 | 4.014236 |
| T, top | 0 | 12.206556 |
| right | 5.734623 | 8.192319 |
| G, centroid | 0 | 6.103278 |

Every coordinate comes from `tools/build_brand.py`. **Never edit an SVG in
`teeter/brand/` by hand** and never place a point by eye; change the builder and
run `python3 tools/build_brand.py`.

| Asset | Use |
| --- | --- |
| `teeter-mark.svg` | the full mark: block on a fixed support, hatched at 35°. 48 px / 12 mm and up |
| `teeter-mark-plain.svg` | no hatch, for 20–48 px |
| `favicon.svg` | 16 and 32 px, on its own graphite square |
| `teeter-lockup.svg` | the mark's ground line is the wordmark's baseline. 120 px / 30 mm wide and up |
| `teeter-lockup-stacked.svg` | mark centred over the wordmark |
| `teeter-mark-construction.svg` | the dimensioned drawing (TT-001) |

Clear space is 3.5 modules, half the block's short side, on every side.
Vellum on graphite, or graphite on vellum; nothing else.

**Never**: at another angle (at 30° it stands, at 40° it has fallen); without
its ground (it is only balanced because something holds it); as an outline
(outlines are for drawings *of* the mark); split along its diagonal (tried, it
reads as a sail).

The wordmark is drawn on the block's module: cap height 10, stems 1.50,
horizontals 1.28, the R's leg at 35° from vertical. Spacing is in `KERN`.

## Tone, and the absence of colour

There is no colour. Contrast is measured against Graphite 950 by `contrast()`
in `build_brand.py`; text pairs must reach 4.5:1.

| Step | Hex | vs 950 | Role |
| --- | --- | --- | --- |
| Graphite 950 | `#0B0B0A` | 1.00 | ground |
| Graphite 900 | `#111110` | 1.04 | sheet |
| Graphite 850 | `#171716` | 1.10 | well |
| Graphite 800 | `#21211F` | 1.22 | grid, hairlines |
| Graphite 700 | `#34332F` | 1.56 | rules |
| Graphite 500 | `#5F5D57` | 2.99 | lines only, **never text** |
| Graphite 400 | `#8E8B83` | 5.79 | tertiary text (5.27 on 850) |
| Graphite 300 | `#B5B1A8` | 9.21 | secondary text |
| Vellum 100 | `#E9E6DE` | 15.79 | text |
| Vellum 50 | `#F5F3EE` | 17.76 | emphasis |

**Failure is hatching at 35°, and nothing else.** It survives a black-and-white
print of a safety appendix, which red does not.

```css
background: repeating-linear-gradient(145deg, var(--ink) 0 1px, transparent 1px 6px);
```
```xml
<pattern id="hx" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-35)">
  <line x1="0" y1="0.5" x2="6" y2="0.5"/></pattern>
```

Lettering never sits on hatching unprotected: give SVG labels a halo
(`paint-order: stroke` in the background colour) and put a hatched swatch
*beside* a word rather than behind it. The one element a reader must not miss is
set by **inversion**, Graphite 950 on Vellum 100.

## Type

- **Archivo**, variable, width 62–125% and weight 100–900. Titles at 125%
  width, headings 112.5–118%, running text 100%.
- **B612 Mono**, designed for Airbus cockpit displays (Intactile DESIGN and
  ENAC, 2012), for every value, unit, field name, caption and code sample. Both
  faces are SIL OFL.
- Archivo has no θ. B612 Mono's Latin subset lacks θ ₀ → √ ≈ ± ∠ × ≤ ≥, so
  `tools/fetch_fonts.py teeter` fetches a second subset with exactly those.
  Write subscripts as a `<tspan>`, not as a Unicode subscript.
- B612 Mono's full stop sits left in its cell, so a mono number inside a sans
  sentence reads as "2. 7". In prose, keep numbers in Archivo with
  `tabular-nums`; use mono for lines that are mono throughout.

## Drawing conventions

| Line, after ISO 128 | Class | For |
| --- | --- | --- |
| thick continuous | `.k` | outlines: the block, the ground |
| thin continuous | `.n` | dimensions, extension lines, leaders |
| thin, hatching | `.ht`, `.hp` | sections, the fixed support, failure |
| long-dashed double-dotted | `.ph` | centroidal lines and alternative positions of a moving part |
| dashed thin | `.limit` | a threshold, such as `tilt_deg > 35` |

Also: the free-body-diagram fixed-support symbol, the quartered-circle
centre-of-gravity symbol, numbered balloons, zones 1–8 across and A–D down, a
title block on every sheet (Title, Dwg no, Rev, Scale, Sheet, Date), NTS where
not to scale. Drawing numbers: TT-000–TT-010 the identity standard, TT-100–TT-109
the website and its sections, TT-201 a report cover.

## Figures are generated, never typed

Every number and chart on `teeter/index.html` is filled by
`python3 tools/build_teeter_site.py` from `assets/data/campaign.json` and
`media/sim.json`, into `<!-- gen:name -->` regions and `data-v="key"` elements.
It stops if the breach time recomputed from the captured physics disagrees with
the record. `harness/tests/test_teeter_site.py` fails when the page is stale,
when the config sample stops loading, or when the axis table or signal list
drifts from `_AXIS_BY_NAME` and `Trajectory`. Add `--og` to re-render
`teeter/assets/og.png` (needs Playwright; `CHROMIUM=` names a browser binary).

Inside an SVG, set lettering as `calc(11px * var(--k))`: `site.js` sets `--k` to
viewBox width over rendered width, so labels stay one size however far the
drawing scales. A figure too wide for a phone is drawn twice (`fig--wide`,
`fig--narrow`) and a container query at 560 px picks one.

## Motion

The opening is a 3D replay of the real simulated robot (three.js, wireframe in
the drawing's line types) from `media/sim.json`: the push, the fall, the pose
at the breach left behind in phantom line, a HUD reading the recorded tilt. It
is labelled as a replay of recorded data and never shows anything the record
does not hold. Scroll motion is GSAP with ScrollTrigger, both in
`teeter/vendor/`. The block in the contact section tips from upright to θc about
P, 2.6 s, cubic in-out, with a live θ readout, when it comes into view. Recorded traces then draw at a
constant rate when they come into view, because they are recordings; the breach
marker lands when the line reaches it (`--hit-frac`, an arc-length fraction from
the builder). The reduction line walks down to the minimal case (`--walk`).
Every start-state is gated on the `.js` class; with no script, or with reduced
motion, the page shows the final state and the replay button is hidden.

## Voice

CLAUDE.md's standing rules are the voice. In practice:

| Not | Instead |
| --- | --- |
| Teeter makes your robot safe. | Teeter found 2 conditions under which your policy breached `tilt_deg > 35.0`. |
| A 41% failure rate. | 41.1% of directed samples violated a predicate. That describes the search, not the robot. |
| A push of 7.875 N·s. | A requested push of 7.875 N·s. |
| Certified. Validated. Compliant. | Reproducible: every result re-runs from its seeds. |

- A rate comes only from the uniform arm, with its interval, and only over the
  box that was declared: 29 of 750, 95% Wilson interval 2.7–5.5%.
- Reduction applies to the most severe failures (`reduce.max`), not to every one.
- `hello@teeter.dev` is **invented**: no mailbox exists and teeter.dev is not
  registered to us. Wherever it appears, say so beside it.
- Say what exists today: one robot model, a baseline policy that holds a stance
  rather than a trained one, no customers, no pilots, no hardware tests.
