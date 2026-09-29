# Brand reel

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
