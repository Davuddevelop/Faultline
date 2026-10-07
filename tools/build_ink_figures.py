#!/usr/bin/env python3
"""Draw the ink cut's figures from the data they claim to show.

Every figure on ink/index.html is generated here from two files:

  assets/data/campaign.json   the published campaign of 2026-08-22
  media/sim.json              the tilt captured by media/capture_sim.py

so no number on that page is typed by hand. The script edits
ink/index.html in place, replacing the contents of each region marked

    <!-- fig:name -->  ...  <!-- /fig:name -->

and filling every <span data-v="dotted.path">…</span> with the value at
that path. Run it after either data file changes:

    python3 tools/build_ink_figures.py

It prints the derived figures it used, including the first breach time,
which is recomputed from the captured tilt rather than read from the
campaign's own record — if the two ever disagree, the page is stale.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "ink" / "index.html"


# ── tiny plotting helpers ────────────────────────────────────────────
def scale(domain, rng):
    (d0, d1), (r0, r1) = domain, rng
    span = (d1 - d0) or 1.0
    return lambda v: r0 + (v - d0) / span * (r1 - r0)


def path(points):
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points)


def arc_fraction(points, index):
    """How far along a polyline, by length, the point at `index` sits.

    The trace is drawn by animating stroke-dashoffset against pathLength="1",
    so progress through the animation is a fraction of arc length, not of x.
    The marker at the breach has to fire at that fraction or it lands on bare
    canvas."""
    cum, total = [0.0], 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        total += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        cum.append(total)
    return cum[index] / total if total else 0.0


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# The record spells units so they survive as JSON keys and filenames. These are
# the same units set the way they are written down.
UNIT_DISPLAY = {"N.s": "N·s", "deg": "deg", "%": "%"}


def unit(u):
    return esc(UNIT_DISPLAY.get(u, u))


# ── figures ──────────────────────────────────────────────────────────
def fig_trace(c, s):
    """Measured body tilt: the nominal run against the smallest failing one."""
    hz = s["hz"]
    nominal, minimal = s["runs"]["nominal"], s["runs"]["minimal"]
    thr = next(p for p in c["report"]["predicates"] if p["name"] == "tilt_limit")["threshold"]

    dur = (len(minimal["tilt"]) - 1) / hz
    x = scale((0, dur), (66, 752))
    y = scale((0, 180), (262, 26))

    def series(tilt):
        return [(x(i / hz), y(v)) for i, v in enumerate(tilt)]

    breach_i = next(i for i, v in enumerate(minimal["tilt"]) if v > thr)
    breach_t = breach_i / hz

    grid = "".join(
        f'<line x1="66" y1="{y(v):.1f}" x2="752" y2="{y(v):.1f}"/>' for v in (90, 135, 180)
    )
    yticks = "".join(
        f'<text x="58" y="{y(v) + 3.5:.1f}" text-anchor="end">{v}</text>' for v in (0, 35, 90, 135, 180)
    )
    xticks = "".join(
        f'<text x="{x(v):.1f}" y="282" text-anchor="middle">{v}</text>' for v in range(0, int(dur) + 1)
    )

    # The draw begins at DRAW_DELAY and runs for DRAW_DUR (see site.css); the
    # marker fires when the drawn line actually reaches the crossing.
    DRAW_DELAY, DRAW_DUR = 0.25, 2.4
    frac = arc_fraction(series(minimal["tilt"]), breach_i)
    hit_at = DRAW_DELAY + frac * DRAW_DUR

    return f'''<svg class="fig fig--trace" viewBox="0 0 780 300" role="img"
     style="--hit-delay:{hit_at:.2f}s;--hit-frac:{frac:.4f}"
     aria-label="Measured body tilt against time. The nominal run stays near zero
     for the whole five seconds. The smallest failing run crosses the 35 degree
     limit at {breach_t:.2f} seconds and continues over.">
  <g class="fig__grid">{grid}</g>
  <g class="fig__axis"><line x1="66" y1="26" x2="66" y2="262"/><line x1="66" y1="262" x2="752" y2="262"/></g>
  <g class="fig__tick">{yticks}{xticks}
    <text x="752" y="282" text-anchor="end" class="fig__unit">seconds</text>
    <text x="66" y="14" text-anchor="start" class="fig__unit">tilt · deg</text>
  </g>
  <line class="fig__limit" x1="66" y1="{y(thr):.1f}" x2="752" y2="{y(thr):.1f}"/>
  <text class="fig__label" x="74" y="{y(thr) - 9:.1f}">tilt_deg &gt; {thr}</text>
  <path class="fig__line fig__line--calm" pathLength="1" d="{path(series(nominal['tilt']))}"/>
  <path class="fig__line fig__line--fail" pathLength="1" d="{path(series(minimal['tilt']))}"/>
  <text class="fig__label fig__label--dim" x="{x(3.6):.1f}" y="{y(6):.1f}">nominal · peak {max(nominal['tilt']):.2f}°</text>
  <circle class="fig__ping" cx="{x(breach_t):.1f}" cy="{y(thr):.1f}" r="4" vector-effect="non-scaling-stroke"/>
  <circle class="fig__hit" cx="{x(breach_t):.1f}" cy="{y(thr):.1f}" r="4"/>
  <text class="fig__label fig__label--hit" x="{x(breach_t) + 12:.1f}" y="{y(thr) - 9:.1f}">breach · {breach_t:.2f}s</text>
</svg>'''


def fig_scatter(c):
    """Where the search actually put its 150 evaluations."""
    sc = c["scatter"]
    (x0, x1), (y0, y1) = sc["x_bounds"], sc["y_bounds"]
    x = scale((x0, x1), (62, 488))
    y = scale((y0, y1), (376, 24))

    dots = []
    for p in sc["points"]:
        cls = "fig__dot fig__dot--fail" if p["f"] else "fig__dot"
        dots.append(f'<circle class="{cls}" cx="{x(p["x"]):.1f}" cy="{y(p["y"]):.1f}" r="{3.4 if p["f"] else 2.6}"/>')

    fails = sum(1 for p in sc["points"] if p["f"])
    grid = "".join(f'<line x1="62" y1="{y(v):.1f}" x2="488" y2="{y(v):.1f}"/>'
                   for v in (y0 + (y1 - y0) * k / 3 for k in (1, 2, 3)))

    return f'''<svg class="fig fig--scatter" viewBox="0 0 520 410" role="img"
     aria-label="All {len(sc['points'])} evaluations of the campaign, plotted by requested
     push impulse against requested torque loss. {fails} of them violated a predicate, and they
     cluster at the high-impulse edge of the declared space.">
  <g class="fig__grid">{grid}</g>
  <g class="fig__axis"><line x1="62" y1="24" x2="62" y2="376"/><line x1="62" y1="376" x2="488" y2="376"/></g>
  <g class="fig__tick">
    <text x="54" y="380" text-anchor="end">{y0:g}</text><text x="54" y="28" text-anchor="end">{y1:g}</text>
    <text x="62" y="396" text-anchor="start">{x0:g}</text><text x="488" y="396" text-anchor="end">{x1:g}</text>
    <text x="62" y="14" text-anchor="start" class="fig__unit">{esc(sc['y_axis'])} · {unit(c['report']['coverage']['per_axis'][sc['y_axis']]['unit'])}</text>
    <text x="488" y="406" text-anchor="end" class="fig__unit">{esc(sc['x_axis'])} · {unit(c['report']['coverage']['per_axis'][sc['x_axis']]['unit'])}</text>
  </g>
  <g class="fig__dots">{''.join(dots)}</g>
</svg>'''


def fig_efficiency(c):
    """Cumulative failures per evaluation: five random seeds against five directed."""
    eff = c["efficiency"]
    budget = c["budget"]
    top = max(max(run) for runs in eff.values() for run in runs)
    x = scale((0, budget), (62, 752))
    y = scale((0, top), (252, 26))

    def lines(runs, cls):
        return "".join(
            f'<path class="fig__line {cls}" pathLength="1" d="{path([(x(i + 1), y(v)) for i, v in enumerate(run)])}"/>'
            for run in runs
        )

    grid = "".join(f'<line x1="62" y1="{y(v):.1f}" x2="752" y2="{y(v):.1f}"/>'
                   for v in (top / 3, 2 * top / 3, top))

    return f'''<svg class="fig fig--eff" viewBox="0 0 780 290" role="img"
     aria-label="Cumulative violations against evaluations spent, five seeds of random
     sampling against five of directed search. Every directed seed finds several times
     what any random seed finds within the same budget of {budget}.">
  <g class="fig__grid">{grid}</g>
  <g class="fig__axis"><line x1="62" y1="26" x2="62" y2="252"/><line x1="62" y1="252" x2="752" y2="252"/></g>
  <g class="fig__tick">
    <text x="54" y="256" text-anchor="end">0</text>
    <text x="54" y="{y(top) + 3.5:.1f}" text-anchor="end">{top}</text>
    <text x="62" y="272" text-anchor="start">0</text>
    <text x="752" y="272" text-anchor="end">{budget}</text>
    <text x="752" y="286" text-anchor="end" class="fig__unit">evaluations</text>
    <text x="62" y="14" text-anchor="start" class="fig__unit">cumulative violations</text>
  </g>
  <g class="fig__band">{lines(eff['random'], 'fig__line--calm')}</g>
  <g class="fig__band">{lines(eff['cem'], 'fig__line--fail')}</g>
  <text class="fig__label fig__label--hit" x="{x(112):.1f}" y="{y(top * 0.86):.1f}">directed (cem)</text>
  <text class="fig__label fig__label--dim" x="{x(112):.1f}" y="{y(top * 0.14):.1f}">random</text>
</svg>'''


def fig_coverage(c):
    """Declared range against the part of it the campaign actually reached."""
    rows = []
    for name, a in c["report"]["coverage"]["per_axis"].items():
        lo, hi = a["declared_min"], a["declared_max"]
        span = (hi - lo) or 1.0
        frm = (a["sampled_min"] - lo) / span * 100
        wid = (a["sampled_max"] - a["sampled_min"]) / span * 100
        rows.append(f'''      <li class="axis">
        <span class="axis__name mono">{esc(name)}</span>
        <span class="axis__track"><span class="axis__span" style="--from:{frm:.2f}%;--span:{wid:.2f}%"></span></span>
        <span class="axis__nums mono">{a['sampled_min']:g} – {a['sampled_max']:g}<i>of {lo:g} – {hi:g} {unit(a['unit'])}</i></span>
      </li>''')
    return '<ul class="axes" data-stagger>\n' + "\n".join(rows) + "\n    </ul>"


def fig_threshold(c):
    """The signature: what the search reached, and what reduction proved underneath it."""
    mode = c["report"]["modes"][0]
    axis = mode["required"][0]
    a = c["report"]["coverage"]["per_axis"][axis]
    lo, hi = a["declared_min"], a["declared_max"]
    span = (hi - lo) or 1.0

    fails = [p["x"] for p in c["scatter"]["points"] if p["f"]]
    f_lo, f_hi = min(fails), max(fails)
    minimal = mode["minimal"][axis]

    frm = (f_lo - lo) / span * 100
    wid = (f_hi - f_lo) / span * 100
    at = (minimal - lo) / span * 100

    return f'''<div class="rule-fig" style="--from:{frm:.2f}%;--span:{wid:.2f}%;--at:{at:.2f}%">
        <div class="rule-fig__head mono"><span>{esc(axis)}</span><span>{unit(a['unit'])}</span></div>
        <div class="rule-fig__track"><span class="rule-fig__band"></span><span class="rule-fig__min"></span></div>
        <div class="rule-fig__foot mono"><span>{lo:g}</span><span>{hi:g}</span></div>
        <dl class="rule-fig__key">
          <dt><span class="swatch swatch--band"></span>Sampled failures ran</dt><dd class="mono">{f_lo:.3f} – {f_hi:.3f}</dd>
          <dt><span class="swatch swatch--min"></span>Reduction proved</dt><dd class="mono">{minimal:.3f}</dd>
        </dl>
      </div>'''


# ── values referenced inline in the prose ────────────────────────────
def values(c, s):
    hz = s["hz"]
    tilt = s["runs"]["minimal"]["tilt"]
    thr = next(p for p in c["report"]["predicates"] if p["name"] == "tilt_limit")["threshold"]
    breach = next(i for i, v in enumerate(tilt) if v > thr) / hz

    r, m = c["totals"]["random"], c["totals"]["cem"]
    rate = lambda xs: 100 * (sum(xs) / len(xs)) / c["budget"]
    cov = c["report"]["coverage"]
    fails = [p["x"] for p in c["scatter"]["points"] if p["f"]]
    mode = c["report"]["modes"][0]

    v = {
        "generated": c["generated"],
        "budget": c["budget"],
        "seeds": f"{min(c['seeds'])}–{max(c['seeds'])}",
        "failures": c["report"]["failures_total"],
        "reduced": c["report"]["reduced"],
        "cells_visited": cov["cells_visited"],
        "cells_total": cov["cells_total"],
        "coverage_pct": f"{100 * cov['fraction_visited']:.2f}",
        "bins": cov["bins_per_axis"],
        "axes_varied": len(cov["per_axis"]),
        "rate_random": f"{rate(r):.1f}",
        "rate_cem": f"{rate(m):.1f}",
        "threshold": f"{thr:g}",
        "breach_t": f"{breach:.2f}",
        "peak_nominal": f"{max(s['runs']['nominal']['tilt']):.2f}",
        "minimal_push": f"{mode['minimal']['push_impulse_ns']:g}",
        "fail_lo": f"{min(fails):.3f}",
        "fail_hi": f"{max(fails):.3f}",
        "mujoco": c["report"]["environment"]["mujoco"],
        "python": c["report"]["environment"]["python"],
        "hz": hz,
    }
    for i, mode in enumerate(c["report"]["modes"]):
        v[f"mode{i}.label"] = mode["label"]
        v[f"mode{i}.count"] = mode["count"]
        v[f"mode{i}.first_t"] = f"{mode['first_t']:.2f}"
        v[f"mode{i}.minimal"] = " · ".join(f"{k} {x:g}" for k, x in mode["minimal"].items())
    return v


# ── injection ────────────────────────────────────────────────────────
def main():
    campaign = json.loads((ROOT / "assets/data/campaign.json").read_text())
    sim = json.loads((ROOT / "media/sim.json").read_text())

    figs = {
        "trace": fig_trace(campaign, sim),
        "scatter": fig_scatter(campaign),
        "efficiency": fig_efficiency(campaign),
        "coverage": fig_coverage(campaign),
        "threshold": fig_threshold(campaign),
    }
    vals = values(campaign, sim)

    html = PAGE.read_text()
    missing = [k for k in figs if f"<!-- fig:{k} -->" not in html]
    if missing:
        sys.exit(f"page has no region for: {', '.join(missing)}")

    for name, svg in figs.items():
        html = re.sub(
            rf"(<!-- fig:{name} -->).*?(<!-- /fig:{name} -->)",
            lambda m: m.group(1) + "\n      " + svg + "\n      " + m.group(2),
            html, flags=re.S,
        )

    unknown = set()

    def put(m):
        key = m.group(1)
        if key not in vals:
            unknown.add(key)
            return m.group(0)
        return f'<span data-v="{key}">{esc(vals[key])}</span>'

    html = re.sub(r'<span data-v="([\w.]+)">.*?</span>', put, html, flags=re.S)
    if unknown:
        sys.exit(f"page asks for values that are not derived: {', '.join(sorted(unknown))}")

    PAGE.write_text(html)

    # The campaign records its own first breach time; the capture recomputes it
    # from the physics. They must agree, or the page is describing an old run.
    recorded = campaign["report"]["modes"][0]["first_t"]
    if abs(float(vals["breach_t"]) - recorded) > 1e-9:
        sys.exit(f"first breach disagrees: captured {vals['breach_t']}s, campaign records {recorded}s")

    print(f"{len(figs)} figures, {len(vals)} values -> {PAGE.relative_to(ROOT)}")
    print(f"  breach {vals['breach_t']}s at {vals['threshold']}° (campaign records {recorded}s)")
    frac = re.search(r"--hit-frac:([\d.]+)", figs["trace"]).group(1)
    print(f"  crossing sits at {frac} of the trace's arc length; marker delay set from it")
    print(f"  hit rate: random {vals['rate_random']}%, directed {vals['rate_cem']}% of {vals['budget']}")
    print(f"  sampled failures {vals['fail_lo']}–{vals['fail_hi']}, reduced to {vals['minimal_push']}")


if __name__ == "__main__":
    main()
