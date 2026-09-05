"""Render report/index.html from a real campaign.

The page is generated, not hand-written, so the numbers on it are the numbers
the harness produced. Re-run after regenerating assets/data/campaign.json.

    python3 tools/build_report_page.py
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "assets" / "data" / "campaign.json").read_text())

# Validated with the dataviz skill's checker against both the panel (#0E1A14)
# and page (#050B08) surfaces: normal-vision dE 20.3, deutan 16.2, all six
# checks pass. The site's own sage and glacial fail the normal-vision floor at
# dE 9.8 and cannot carry two series.
GREEN, BLUE = "#2BA476", "#6E89DC"

W, H = 720, 300
PAD_L, PAD_R, PAD_T, PAD_B = 46, 148, 18, 34   # right pad fits swatch + direct label


def esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ───────────────────────────── efficiency chart ─────────────────────────────

def efficiency_svg() -> str:
    eff = DATA["efficiency"]
    budget = DATA["budget"]
    peak = max(max(c) for runs in eff.values() for c in runs)
    # round the axis to a step a reader can do arithmetic on
    raw = peak / 4
    mag = 10 ** int(max(0, len(str(int(raw))) - 1))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    step = int(step)
    ymax = -(-peak // step) * step

    def X(i: int) -> float:
        return PAD_L + i / (budget - 1) * (W - PAD_L - PAD_R)

    def Y(v: float) -> float:
        return H - PAD_B - v / ymax * (H - PAD_T - PAD_B)

    parts: list[str] = []

    # recessive grid
    for gv in range(0, ymax + 1, step):
        parts.append(f'<line class="grid" x1="{PAD_L}" y1="{Y(gv):.1f}" x2="{W-PAD_R}" y2="{Y(gv):.1f}"/>')
        parts.append(f'<text class="tick" x="{PAD_L-9}" y="{Y(gv)+3.5:.1f}" text-anchor="end">{gv}</text>')
    for gx in (0, 50, 100, budget - 1):
        parts.append(f'<text class="tick" x="{X(gx):.1f}" y="{H-PAD_B+17}" text-anchor="middle">{gx+1 if gx else 1}</text>')

    for method, colour in (("random", GREEN), ("cem", BLUE)):
        runs = eff[method]
        # every seed, faint — the spread is part of the result
        for curve in runs:
            d = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(curve))
            parts.append(f'<path class="seed" d="{d}" stroke="{colour}"/>')
        # median across seeds, solid
        med = [st.median(vals) for vals in zip(*runs)]
        d = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(med))
        parts.append(f'<path class="median" d="{d}" stroke="{colour}"/>')
        # Direct label. The text wears ink, not the series colour — a short
        # coloured rule beside it carries identity, so the label survives any
        # colour-vision deficiency and is not relying on hue to be read.
        label = "directed (CEM)" if method == "cem" else "random"
        ly = Y(med[-1])
        parts.append(
            f'<line class="swatch" x1="{W-PAD_R+8}" y1="{ly:.1f}" '
            f'x2="{W-PAD_R+24}" y2="{ly:.1f}" stroke="{colour}"/>'
        )
        parts.append(f'<text class="lbl" x="{W-PAD_R+30}" y="{ly+4:.1f}">{label}</text>')
        parts.append(
            f'<text class="lblnum" x="{W-PAD_R+30}" y="{ly+19:.1f}">median {med[-1]:.0f}</text>'
        )

    return (
        f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Cumulative violations '
        f'found against simulations spent. Directed search reaches a median of '
        f'{st.median([len(c) and c[-1] for c in eff["cem"]]):.0f} violations; random reaches '
        f'{st.median([c[-1] for c in eff["random"]]):.0f}.">'
        + "".join(parts)
        + f'<line class="axis" x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H-PAD_B}"/>'
        + f'<line class="axis" x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-PAD_R}" y2="{H-PAD_B}"/>'
        + "</svg>"
    )


# ─────────────────────────────── scatter ───────────────────────────────────

def scatter_svg() -> str:
    sc = DATA["scatter"]
    xlo, xhi = sc["x_bounds"]
    ylo, yhi = sc["y_bounds"]
    w, h = 720, 320
    pl, pr, pt, pb = 52, 20, 18, 40

    def X(v: float) -> float:
        return pl + (v - xlo) / (xhi - xlo) * (w - pl - pr)

    def Y(v: float) -> float:
        return h - pb - (v - ylo) / (yhi - ylo) * (h - pt - pb)

    parts = []
    for gv in range(0, int(yhi) + 1, 5):
        parts.append(f'<line class="grid" x1="{pl}" y1="{Y(gv):.1f}" x2="{w-pr}" y2="{Y(gv):.1f}"/>')
        parts.append(f'<text class="tick" x="{pl-9}" y="{Y(gv)+3.5:.1f}" text-anchor="end">{gv}</text>')
    for gv in range(0, int(xhi) + 1, 3):
        parts.append(f'<text class="tick" x="{X(gv):.1f}" y="{h-pb+17}" text-anchor="middle">{gv}</text>')

    # passes first, so failures sit on top
    for p in sc["points"]:
        if not p["f"]:
            parts.append(f'<circle class="pass" cx="{X(p["x"]):.1f}" cy="{Y(p["y"]):.1f}" r="3.2"/>')
    for p in sc["points"]:
        if p["f"]:
            parts.append(
                f'<circle class="fail" cx="{X(p["x"]):.1f}" cy="{Y(p["y"]):.1f}" r="4.4" fill="{BLUE}"/>'
            )

    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Each of 150 simulations '
        f'plotted by push impulse and actuator torque loss. Violations cluster at high '
        f'push impulse.">'
        + "".join(parts)
        + f'<line class="axis" x1="{pl}" y1="{pt}" x2="{pl}" y2="{h-pb}"/>'
        + f'<line class="axis" x1="{pl}" y1="{h-pb}" x2="{w-pr}" y2="{h-pb}"/>'
        + f'<text class="axname" x="{(pl+w-pr)/2:.0f}" y="{h-4}" text-anchor="middle">'
        f'push impulse (N·s)</text>'
        + f'<text class="axname" transform="rotate(-90 14 {(pt+h-pb)/2:.0f})" x="14" '
        f'y="{(pt+h-pb)/2:.0f}" text-anchor="middle">actuator torque loss (%)</text>'
        + "</svg>"
    )


def modes_html() -> str:
    rows = []
    for i, m in enumerate(DATA["report"]["modes"], 1):
        cond = "".join(
            f'<div class="kv"><span>{esc(a)}</span><b>{v:g}</b></div>'
            for a, v in m["minimal"].items()
        )
        rows.append(f"""
      <article class="mode">
        <p class="mode__n mono">mode {i} — {m['count']} of {DATA['report']['reduced']} reduced</p>
        <h3>{esc(' + '.join(m['required']))}</h3>
        <p class="mode__p">Minimal condition that still violates
          <code>{esc(m['label'].split(' via ')[0])}</code>, first firing at
          t&nbsp;=&nbsp;{m['first_t']}s. Found in {m['evaluations']} simulations.</p>
        <div class="kvs">{cond}</div>
      </article>""")
    return "".join(rows)


def build() -> Path:
    r = DATA["report"]
    cov = r["coverage"]
    tot = DATA["totals"]
    med_random, med_cem = st.median(tot["random"]), st.median(tot["cem"])

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sample report — Faultline</title>
<meta name="description" content="Real output from a Faultline campaign: failure modes, sample efficiency and coverage, generated by the harness on a stand-in quadruped.">
<meta name="theme-color" content="#050B08">
<link rel="preload" href="../assets/fonts/jizBRFtNs2ka5fXjeivQ4LroWlx-6zsTjmbI.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../css/fonts.css">
<link rel="stylesheet" href="../css/site.css">
<link rel="stylesheet" href="report.css">
<link rel="icon" href="../assets/favicon.svg" type="image/svg+xml">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

<header class="nav is-stuck" id="nav">
  <div class="nav__in">
    <a class="mark" href="../index.html"><svg class="mark__glyph" viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="3.5" width="13" height="4.6" fill="currentColor"/><rect x="2.5" y="8.9" width="10" height="4.6" fill="currentColor"/><rect x="2.5" y="14.3" width="16.5" height="4.6" fill="currentColor"/></svg>Faultline</a>
    <a class="nav__cta" href="../index.html#contact">Talk to us</a>
  </div>
</header>

<main id="main">
<section class="rep-head">
  <div class="wrap">
    <p class="eyebrow">Sample report</p>
    <h1 class="display">What a campaign actually produces.</h1>
    <p class="rep-lede">Everything below is real output from the harness — a campaign
      of {DATA['budget']} simulations against a stand-in 12-DOF quadruped and a
      baseline stance controller. It is not a customer's robot, and it is not a
      mockup. The numbers are the numbers the harness printed.</p>
    <p class="note mono">Generated {DATA['generated']} · mujoco {r['environment']['mujoco']} · {r['environment']['platform']}</p>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="head"><h2 class="h2">Where the budget went.</h2>
      <p class="head__lede">Cumulative violations found against simulations spent,
        five seeds per method. Faint lines are individual seeds; the solid line is
        the median. Both methods spent exactly {DATA['budget']} simulations.</p></div>
    <figure class="chart">
      {efficiency_svg()}
      <figcaption>
        Directed search reached a median of {med_cem:.0f} violations against random's
        {med_random:.0f}. It does <em>not</em> find the first violation sooner — its
        opening round is uniform sampling, so it has no head start. The difference is
        what happens to the rest of the budget. Five seeds is a description, not a
        significance test.
      </figcaption>
    </figure>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="head"><h2 class="h2">Failures grouped by what they need.</h2>
      <p class="head__lede">The {r['reduced']} most severe of {r['failures_total']}
        violations were minimised — each perturbation relaxed toward nominal for as
        long as the failure survived. Two runs are the same mode when they reduce to
        the same required axes.</p></div>
    <div class="modes">{modes_html()}</div>
    <p class="note mono">Grouping is by reduced form, not by a learned classifier. Only
      the {r['reduced']} most severe were reduced, so this grouping is not exhaustive.</p>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="head"><h2 class="h2">The space, and what was covered of it.</h2></div>
    <div class="stat">
      <p class="stat__n mono">{cov['fraction_visited']*100:.2f}%</p>
      <p class="stat__p">of the declared parameter space was visited —
        {cov['cells_visited']} of {cov['cells_total']} cells, partitioning each of the
        {len(DATA['space'])} axes into {cov['bins_per_axis']} bins. This campaign
        <em>sampled</em> the volume; it did not sweep it. Behaviour in unvisited
        regions is unsupported by this evidence.</p>
    </div>
    <figure class="chart">
      {scatter_svg()}
      <figcaption>
        Every simulation in one directed campaign, plotted against the two axes the
        reduction found to matter.
        <span class="key"><span class="dot dot--fail"></span>violated the tilt limit</span>
        <span class="key"><span class="dot dot--pass"></span>did not</span>
        Directed sampling concentrates toward high push impulse, which is where the
        boundary is.
      </figcaption>
    </figure>
  </div>
</section>

<section class="section">
  <div class="wrap">
    <div class="head"><h2 class="h2">What this report does not say.</h2></div>
    <ul class="rules mono">
      <li>No claim that the policy is safe. This campaign found violations; it cannot show their absence.</li>
      <li>No claim of conformity with any regulation or standard.</li>
      <li>Findings apply to the declared space above and to no condition outside it.</li>
      <li>Minimal cases are locally minimal — no single axis relaxes further, but a different combination may be smaller.</li>
      <li>The robot is a stand-in and the policy is a stance controller, not a trained one.</li>
    </ul>
  </div>
</section>

<section class="contact" id="contact">
  <div class="wrap contact__in">
    <p class="eyebrow">Talk to us</p>
    <h2 class="h2">Want this run against your policy?</h2>
    <p>Send us a checkpoint, a robot model and the limits that matter for your machine.
      We are looking for design partners, not customers — there is no product to buy yet.</p>
    <a class="btn btn--lg" href="../index.html#contact">Start a conversation <span aria-hidden="true">&rarr;</span></a>
  </div>
</section>
</main>

<footer class="foot">
  <div class="wrap foot__in">
    <span class="mono">Faultline — pre-product · Baku, Azerbaijan</span>
    <span class="mono"><a href="../index.html">Back to the site</a></span>
  </div>
</footer>
</body>
</html>
"""
    out = ROOT / "report" / "index.html"
    out.write_text(page)
    return out


if __name__ == "__main__":
    print("wrote", build())
