# Brand films

`teeter-ad-1x1.mp4`: 18 s, 1080 × 1080, 30 fps, H.264, no audio. The Teeter ad.

`faultline-ad.mp4` and `faultline-reel.mp4` are films in the previous identity,
withdrawn with it, and their scatter is a seeded point cloud rather than the
campaign's evaluations (see below). Never post them.

## The Teeter ad: `teeter-ad-1x1.mp4`

Four sheets of one drawing, TT-401 to TT-404:

| Sheet | Time | What it shows | Where it comes from |
| --- | --- | --- | --- |
| TT-401 | 0–4.6 s | the stand-in quadruped pushed over: the requested push, the breach of `tilt_deg > 35` at 1.26 s, the pose at the breach left in phantom line | the site's own machine (`teeter/js/machine.js`) replaying the replay document embedded in `teeter/index.html`, built from `sim.json` |
| TT-402 | 4.5–10.6 s | the declared space, the rules, the 150 directed evaluations in the order they ran, the reduction to 7.875 N·s requested | `assets/data/campaign.json`: `space`, `report.predicates`, `scatter`, `report.modes[0]` |
| TT-403 | 10.7–14.6 s | `teeter gate` blocking `tall-v2`: the push it falls to dropped from 7.875 to 6.89323 N·s requested, exit code 1 | the output of the run on the v0 demo stack on 9 October 2026, typed into the page in the form `cmd_gate` prints (`runner/teeter_runner/cli.py`); the only typed block |
| TT-404 | 14.7–18 s | the lockup, "Adversarial testing for learned robot policies." | `teeter/brand/teeter-lockup.svg` |

What the film says about itself, on screen: the robot is a stand-in and the
body drawn around its recorded poses is illustrative; 38 of 150 is a count of a
directed search, not a failure rate; the gate's checkpoints hold poses and none
is a trained policy. Pushes are requested values throughout.

The end card carries no address: teeter.dev is not registered to us and
`hello@teeter.dev` is invented. Put the link in the post, not in the film.

### Rebuilding

```
pip install playwright imageio-ffmpeg
python3 media/shoot-teeter-ad.py                     # media/teeter-ad-1x1.mp4, about a minute
python3 media/shoot-teeter-ad.py --stills 0,9.6      # single frames as PNG, for review
```

`teeter-ad.html` draws the film as a function of time. The machine runs on a
clock the page steps (its `requestAnimationFrame` is a queue drained once per
frame), so frames must be asked for in order; the shoot script does, and two
renders give identical frames. To watch it in real time, serve the repository
root and open `/media/teeter-ad.html?play`. Fonts are the site's own
(`teeter/css/fonts.css`), so the render needs no network.

Re-render after `assets/data/campaign.json` or `sim.json` changes; the gate's
output on TT-403 has to be re-recorded by hand if the demo changes.

---

# The previous identity's films (withdrawn)

`faultline-ad.mp4`: 34 s, the ad.
`faultline-reel.mp4`: 22 s, an earlier, simpler cut.

## The reel

`faultline-reel.mp4` — 22 s, 1920×1080, 30 fps.

Not stock footage and not generated. `reel.html` is a single canvas whose
`seek(t)` is a pure function of time: nothing persists between frames, so the
render is deterministic and can be stepped rather than captured in real time.

## Rebuilding

```
pip install playwright imageio-ffmpeg
python3 shoot.py                       # writes frames/f0000.png …
ffmpeg -framerate 30 -i frames/f%04d.png \
  -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p -movflags +faststart \
  faultline-reel.mp4
```

`shoot.py` expects `plate.jpg` beside it — use `assets/img/fissure.jpg`, or the
graded version if one has been produced.

## Every figure on screen is real

From the published campaign (`assets/data/campaign.json`, made by `tools/publish_campaign.py`):
150 simulations · 38 violations · 10 reduced · 83 of 4096 cells ·
minimal case 7.875 N·s **requested** · `tilt_deg > 35.0` · first breach 1.26 s.

The scatter is a seeded point cloud that begins uniform and concentrates toward
high impulse — the shape a directed search actually produces. Red marks a
violation.

## Known limits

- No audio.
- Bitstream Charter, not the site's typeface: the build sandbox has no outbound
  access to Google Fonts, so a webfont could not be used in the render.


---

# The ad — `faultline-ad.mp4`

Seven scenes, 34 s. The robot is not an illustration: its body positions come
from `sim.json`, captured by stepping the real MuJoCo model with the real
baseline policy under the real minimal failing condition of 7.875 N·s.

MuJoCo cannot render in this container — no GL libraries — but physics does not
need GL, so the simulation runs headless and the drawing is done in canvas from
the captured geometry, with a perspective camera.

**The capture independently reproduces the campaign.** The minimal case breaches
35° at 1.26 s, matching `first_t` for mode 1 in `assets/data/campaign.json`.
`capture_sim.py` prints this on every run; if it stops matching, the model,
policy or perturbation has changed and the film is stale.

## Rebuilding

```
cd harness && python3 ../media/capture_sim.py     # writes media/sim.json
cd ../media && python3 -m http.server 8802 &      # fetch() is blocked on file://
python3 shoot-ad.py                               # writes frames/
ffmpeg -framerate 30 -i frames/f%04d.png \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -movflags +faststart \
  faultline-ad.mp4
```

`shoot-ad.py` points at port 8802 and `reel2.html`; `ad.html` is that file.

## Known limits

- No audio.
- Bitstream Charter, not the site's typeface — the sandbox has no outbound
  access to Google Fonts, so no webfont could be used in the render.
