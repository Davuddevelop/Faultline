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

## Swapping the hero art

The hero is an inline SVG scene (`.scene` in `index.html`) — layered ridges,
mist, and the fissure, parallaxed on scroll. To replace it with a photo or a
looping video later, drop the file in `assets/` and swap the contents of
`.scene`; the text panel and vignette sit above it and need no changes.
