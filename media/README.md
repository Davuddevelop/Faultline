# Brand films

`faultline-ad.mp4` — 34 s, the ad.
`faultline-reel.mp4` — 22 s, an earlier, simpler cut.

## The ad

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

From the campaign of 2026-08-22 (`assets/data/campaign.json`):
150 simulations · 51 violations · 10 reduced · 87 of 4096 cells ·
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
