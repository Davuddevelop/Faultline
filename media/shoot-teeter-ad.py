"""Render media/teeter-ad.html to an MP4, frame by frame.

The page draws the film as a function of time and runs the site's machine on a
clock it steps, so the frames are asked for in order and piped to ffmpeg; the
result is the same every render. Serves the repository root itself.

    python3 media/shoot-teeter-ad.py                    # media/teeter-ad-1x1.mp4
    python3 media/shoot-teeter-ad.py --stills 0.2,1.6   # PNGs of single frames, for review

Needs Playwright and imageio-ffmpeg (pip install playwright imageio-ffmpeg).
CHROMIUM= names a browser binary when Playwright's own is not installed.
"""
import argparse
import functools
import http.server
import os
import subprocess
import threading
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = "media/teeter-ad.html"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(Quiet, directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def browser(pw):
    exe = os.environ.get("CHROMIUM") or ("/opt/pw-browsers/chromium" if Path("/opt/pw-browsers/chromium").exists() else None)
    args = ["--no-sandbox", "--force-device-scale-factor=1"]
    return pw.chromium.launch(executable_path=exe, args=args) if exe else pw.chromium.launch(args=args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "media/teeter-ad-1x1.mp4"))
    ap.add_argument("--stills", help="comma-separated times in seconds: write PNGs instead of the film")
    ap.add_argument("--still-dir", default=str(ROOT / "media/teeter-ad-stills"))
    args = ap.parse_args()

    httpd = serve()
    url = f"http://127.0.0.1:{httpd.server_address[1]}/{PAGE}"
    with sync_playwright() as pw:
        b = browser(pw)
        page = b.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=1)
        errors, console = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
        page.goto(url)
        try:
            page.wait_for_function("window.READY === true || window.ERROR", polling=100, timeout=60000)
        except Exception:
            raise SystemExit("the page never became ready:\n  " + "\n  ".join((errors + console)[-8:]))
        if page.evaluate("window.ERROR || null"):
            raise SystemExit(f"the page failed: {page.evaluate('window.ERROR')}")
        meta = page.evaluate("window.META")

        if args.stills:
            out = Path(args.still_dir)
            out.mkdir(parents=True, exist_ok=True)
            for t in sorted(float(s) for s in args.stills.split(",")):
                page.evaluate(f"seek({t})")
                page.screenshot(path=str(out / f"t{t:05.2f}.png"))
                print(f"  still {t:.2f} s")
        else:
            ff = subprocess.Popen(
                [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
                 "-f", "image2pipe", "-framerate", str(meta["FPS"]), "-c:v", "png", "-i", "-",
                 "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", args.out],
                stdin=subprocess.PIPE)
            t0 = time.time()
            for i in range(meta["FRAMES"]):
                page.evaluate(f"seek({i / meta['FPS']})")
                ff.stdin.write(page.screenshot(type="png"))
                if i % 90 == 0:
                    print(f"  frame {i} of {meta['FRAMES']}, {time.time() - t0:.0f} s", flush=True)
            ff.stdin.close()
            if ff.wait() != 0:
                raise SystemExit("ffmpeg failed")
            print(f"wrote {args.out} ({meta['FRAMES']} frames, {time.time() - t0:.0f} s)")
        if errors:
            print("page errors:", errors[:3])
        b.close()
    httpd.shutdown()


if __name__ == "__main__":
    main()
