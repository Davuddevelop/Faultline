# Faultline

Landing page for Faultline — adversarial testing for learned robot policies.

Static HTML and CSS. No build step, no framework, no external requests at
runtime: fonts are self-hosted and every image is local.

```
python3 -m http.server 8000     # then open http://localhost:8000
```

## The four pages

One shared content spec, four design directions. Copy, sections and section
order are identical in all of them; only the design language differs.

| Path | Direction | Hero |
| --- | --- | --- |
| `index.html` | **Scene** — no photography at all | Layered SVG landscape: ridges, mist, three quadrupeds, and the fissure drawn with light inside it, parallaxed on scroll |
| `v1/index.html` | **Field** — light and editorial | The photograph, type set into its fog; one dark band (the deadline) breaks the paper |
| `v2/index.html` | **Split** — studio card | One rounded card: image on the left half, type on the right; a second card later flips it |
| `v3/index.html` | **Overlay** — cinematic | Full-bleed image, headline sitting at the bottom of it, centre nav pills, a full-bleed quote plate mid-page |

`v1`–`v3` share `js/variant.js` and `css/fonts.css`. `index.html` has its own
`js/main.js` because its hero is an SVG scene with its own parallax and a
mobile reframe.

## Images

`assets/img/` holds three sources, each as WebP at 800 / 1280 / 2048 and a
JPEG fallback, served through `<picture>` with `srcset`:

- `fissure` — a robot at the edge of a break in the ground, light inside it
- `moss-walk` — a quadruped crossing a mossy ridge in fog
- `valley-line` — robots walking a line across a wide valley

`manifest.json` records each image's dominant colour, which is painted behind
it so there is no flash before it loads. Originals were 3.3 MB PNGs; the whole
directory is now ~1.5 MB.

To swap an image, drop the new file in and regenerate the sizes — nothing else
references the filenames but the `<picture>` blocks.

## Type

Instrument Serif (display, italic for the accented word), IBM Plex Sans
(body, 200–300), IBM Plex Mono (all numbers, labels and eyebrows).
Self-hosted in `assets/fonts/`, declared in `css/fonts.css`.

## The amber rule

`--amber` appears in three places only: the light inside the fissure, the date
20 January 2027, and the single call to action. It reads as a warning exactly
as long as it stays rare. Adding a fourth use makes it decorative and the
visual argument collapses.

## Before this goes live

- **The call to action points at `mailto:hello@faultline.dev`, a placeholder.**
  Replace it in all four pages.
- Verify both paragraphs of the deadline section against EUR-Lex. If a
  notified body engineer corrects any of it, fix the page that day.
- The status section stays. For a safety-evidence product, saying plainly
  what you cannot yet show is the strongest trust signal on the page.

## Verified

All four pages, at 1440 / 768 / 390 and under `prefers-reduced-motion`:
no console errors, no failed requests, no horizontal overflow, every image
loading with alt text, and every reveal firing under normal scrolling.
