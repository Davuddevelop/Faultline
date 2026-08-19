# Faultline

Landing page. Static — no build step. Open `index.html`, or serve the folder.

```
index.html          all markup, plus the inline SVG hero scene
css/styles.css      design tokens + layout
css/fonts.css       self-hosted Instrument Serif / IBM Plex Sans / IBM Plex Mono
js/main.js          scroll reveal, hero parallax, sticky nav (all optional)
assets/fonts/       woff2, so the page has no external dependencies
```

## Before publishing

- Replace `mailto:hello@faultline.dev` in `index.html` with the real address.
- Verify both paragraphs in the deadline section against EUR-Lex.

## The amber rule

`--amber` appears in exactly three places: the crack in the hero, the date
20 January 2027, and the single button. A fourth use makes it decorative and
it stops reading as a warning.

## The hero scene

An inline SVG in `index.html` (`.scene`): layered ridges with atmospheric
depth, drifting mist, three quadrupeds at three scales, and the fissure —
tapering to a point at the horizon, opening toward the viewer, amber light
inside it. Layers carry `data-depth` and parallax on scroll.

The quadruped is one `<g id="quad">` in `<defs>`, reused via `<use>`. Each
instance sets its own `--x`, `--y`, `--s` and takes its body colour from
`color`, so moving one or adding a fourth is a one-line change.

Below 900px `js/main.js` retargets the `viewBox` to `670 412 780 488` — a
phone slices a narrow column out of a 1600-unit scene, which would crop the
crack out entirely. The narrow framing puts the horizon above the text panel
and lets the crack come out from underneath it.

To swap in a photo or a looping video later, drop the file in `assets/` and
replace the contents of `.scene`; the text panel and vignette sit above it
and need no changes.
