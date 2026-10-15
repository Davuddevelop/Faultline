# The ink cut

A second landing page, built after the first one was judged to look like every
other page an AI has built in 2026. Three things changed.

**No photographs.** The earlier page carried three full-bleed generated
illustrations of robots in meadows, which were the loudest signal on it. There
are none here. Every figure is drawn from data the harness produced:

| Figure | From |
| --- | --- |
| Body tilt, nominal against the smallest failing case | `media/sim.json`, captured by `media/capture_sim.py` |
| Where the budget went (150 evaluations) | `assets/data/campaign.json` |
| Sample efficiency, five seeds each | `assets/data/campaign.json` |
| Declared range against what was reached | `assets/data/campaign.json` |
| The reduction, on `push_impulse_ns` | both |

**Near-monochrome.** Greys on `#0E0E0D`. One colour, oxide, and it is reserved
for things that failed — a violating sample, a breached threshold, the trace
that goes over. Any other use of it is a bug. `--oxide` (3.7:1 on the figure
wells) is a mark; `--oxide-t` is the same signal where it has to be read as
text.

**Newsreader, Geist, Geist Mono**, self-hosted, all SIL OFL. Fontshare and
jsDelivr are unreachable from the build container, so the Google Fonts library
is the whole of what could be installed.

## Rebuilding

```sh
python3 tools/build_ink_figures.py   # figures and inline values
python3 tools/fetch_fonts.py         # only if the faces change
```

`build_ink_figures.py` replaces every `<!-- fig:name -->` region and fills every
`<span data-v="path">` in `index.html`, so no number on the page is typed by
hand. It recomputes the first breach time from the captured tilt and fails if
that disagrees with the time the campaign recorded — if it ever does, the page
is describing a run that no longer exists.

It also computes where the 35° crossing sits along the trace's arc length
(0.2416) and writes the marker's animation delay from it, so the violation dot
fires when the drawn line actually reaches the crossing rather than at a moment
picked by eye.

## Known

- `hello@faultline.dev` is **invented**. It is not a configured address, and the
  page says so beneath the link. Replace it before this page is published.
- The campaign is against a stand-in quadruped policy. There are no customer
  results and no completed pilots.
- `35.9%` is a directed-search hit rate, not a failure rate, and the page says
  so next to it. Only the five uniform-random seeds could support a rate, and
  five is nowhere near enough to claim one.
