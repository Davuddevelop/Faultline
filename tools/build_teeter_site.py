#!/usr/bin/env python3
"""Fill the Teeter website from the data it claims to show.

Every figure and every number on teeter/index.html comes from:

  assets/data/campaign.json   the published campaign of 2026-08-22
  media/sim.json              the tilt captured by media/capture_sim.py
  tools/build_brand.py        the mark, its construction and the drawing style

The page is written by hand around marked regions,

    <!-- gen:name -->  ...  <!-- /gen:name -->

which this script replaces, and every element carrying data-v="key" has its
text set to the derived value, whatever the element. Run it after any of the
three changes:

    python3 tools/build_teeter_site.py          # the page
    python3 tools/build_teeter_site.py --og     # and the social card, via Playwright

It refuses to write a page that asks for a value it cannot derive, and it stops
if the breach time recomputed from the captured physics disagrees with the
campaign's own record: then the page would be describing an old run.
"""
from __future__ import annotations

import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_brand as bb            # noqa: E402
import build_ink_figures as ink     # noqa: E402

ROOT = bb.ROOT
SITE = ROOT / "teeter"
PAGE = SITE / "index.html"
f = bb.f


# ── figures the identity standard does not already draw ─────────────────
def scatter_figure(c, pid="hx-scatter"):
    """Where the campaign put its evaluations. Failed runs solid, passing runs
    hollow, and the band every failure fell in hatched at 35 degrees."""
    sc = c["scatter"]
    (x0, x1), (y0, y1) = sc["x_bounds"], sc["y_bounds"]
    per = c["report"]["coverage"]["per_axis"]
    l, r, t, b = 34, 366, 30, 252
    X, Y = ink.scale((x0, x1), (l, r)), ink.scale((y0, y1), (b, t))
    fails = [p for p in sc["points"] if p["f"]]
    f_lo, f_hi = min(p["x"] for p in fails), max(p["x"] for p in fails)

    o = [f"<defs>{bb.hatch_pattern(pid, 5.0)}</defs>"]
    for k in (1, 2):
        yy = Y(y0 + (y1 - y0) * k / 3)
        o.append(f'<line class="grid" x1="{l}" y1="{f(yy)}" x2="{r}" y2="{f(yy)}"/>')
    band = f'x="{f(X(f_lo))}" y="{t}" width="{f(X(f_hi) - X(f_lo))}" height="{b - t}"'
    o.append(f'<rect class="fail-zone" {band} fill="url(#{pid})"/><rect class="fail-edge" {band}/>')
    o.append(f'<line class="axis" x1="{l}" y1="{t}" x2="{l}" y2="{b}"/>'
             f'<line class="axis" x1="{l}" y1="{b}" x2="{r}" y2="{b}"/>')
    for p in sorted(sc["points"], key=lambda p: p["f"]):
        if p["f"]:
            o.append(f'<circle class="dot--fail" cx="{f(X(p["x"]))}" cy="{f(Y(p["y"]))}" r="3.1"/>')
        else:
            o.append(f'<circle class="dot" cx="{f(X(p["x"]))}" cy="{f(Y(p["y"]))}" r="2.5"/>')
    o.append(f'<text class="tick" x="{l - 8}" y="{b + 3.5}" text-anchor="end">{y0:g}</text>'
             f'<text class="tick" x="{l - 8}" y="{t + 3.5}" text-anchor="end">{y1:g}</text>'
             f'<text class="tick" x="{l}" y="{b + 18}" text-anchor="middle">{x0:g}</text>'
             f'<text class="tick" x="{r}" y="{b + 18}" text-anchor="middle">{x1:g}</text>')
    o.append(f'<text class="unit" x="{l}" y="{t - 14}">{ink.esc(sc["y_axis"])} · {ink.unit(per[sc["y_axis"]]["unit"])}</text>'
             f'<text class="unit" x="{r}" y="{b + 36}" text-anchor="end">{ink.esc(sc["x_axis"])} · requested · '
             f'{ink.unit(per[sc["x_axis"]]["unit"])}</text>')
    o.append(f'<text class="lab hi" x="{f(X(f_lo) - 10)}" y="{t + 16}" text-anchor="end">'
             f'{len(fails)} failed, all at ≥ {f_lo:.3f}</text>')
    label = (f"All {len(sc['points'])} evaluations, by requested push impulse against requested torque loss. "
             f"The {len(fails)} that violated a predicate all sit between {f_lo:.3f} and {f_hi:.3f} "
             f"newton-seconds, at the edge of the declared range.")
    return f'<svg class="fig" viewBox="0 0 380 300" role="img" aria-label="{label}">{"".join(o)}</svg>'


def efficiency_figure(c):
    """Cumulative violations against budget spent, every seed of each method.
    The same size as the scatter, which it sits beside."""
    eff, budget = c["efficiency"], c["budget"]
    top = max(max(run) for runs in eff.values() for run in runs)
    l, r, t, b = 34, 366, 30, 252
    X, Y = ink.scale((0, budget), (l, r)), ink.scale((0, top), (b, t))

    def lines(runs, cls):
        return "".join(f'<path class="{cls}" d="{ink.path([(X(i + 1), Y(v)) for i, v in enumerate(run)])}"/>'
                       for run in runs)

    o = []
    for k in (1, 2, 3):
        yy = Y(top * k / 3)
        o.append(f'<line class="grid" x1="{l}" y1="{f(yy)}" x2="{r}" y2="{f(yy)}"/>')
    o.append(f'<line class="axis" x1="{l}" y1="{t}" x2="{l}" y2="{b}"/>'
             f'<line class="axis" x1="{l}" y1="{b}" x2="{r}" y2="{b}"/>')
    o.append(lines(eff["random"], "run-calm") + lines(eff["cem"], "run-dir"))
    o.append(f'<text class="tick" x="{l - 8}" y="{b + 3.5}" text-anchor="end">0</text>'
             f'<text class="tick" x="{l - 8}" y="{f(Y(top) + 3.5)}" text-anchor="end">{top}</text>'
             f'<text class="tick" x="{l}" y="{b + 18}" text-anchor="middle">0</text>'
             f'<text class="tick" x="{r}" y="{b + 18}" text-anchor="middle">{budget}</text>')
    o.append(f'<text class="unit" x="{l}" y="{t - 14}">cumulative violations</text>'
             f'<text class="unit" x="{r}" y="{b + 36}" text-anchor="end">evaluations</text>')
    hi_cem = max(run[-1] for run in eff["cem"])
    hi_rnd = max(run[-1] for run in eff["random"])
    # a key in the corner the lines never reach: every run is near zero there
    for i, (cls, text, lab) in enumerate((("run-dir", "directed · cem", "lab hi"),
                                          ("run-calm", "uniform · random", "lab"))):
        ky = t + 16 + i * 20
        o.append(f'<line class="{cls}" x1="{l + 12}" y1="{ky - 4}" x2="{l + 34}" y2="{ky - 4}"/>'
                 f'<text class="{lab}" x="{l + 42}" y="{ky}">{text}</text>')
    n = len(eff["cem"])
    label = (f"Cumulative violations against evaluations spent, {n} seeds of uniform sampling against {n} of "
             f"directed search, {budget} evaluations each. Directed search ends between "
             f"{min(run[-1] for run in eff['cem'])} and {hi_cem}; uniform sampling between "
             f"{min(run[-1] for run in eff['random'])} and {hi_rnd}.")
    return f'<svg class="fig" viewBox="0 0 380 300" role="img" aria-label="{label}">{"".join(o)}</svg>'


def wide_and_narrow(wide, narrow):
    """Two drawings of one figure. A container query shows the narrow one in a
    narrow column, where the wide one would shrink its text to nothing. The
    hidden copy is taken out of the accessibility tree by display:none."""
    return (wide.replace('<svg class="fig"', '<svg class="fig fig--wide"', 1) +
            narrow.replace('<svg class="fig"', '<svg class="fig fig--narrow"', 1))


# The record keeps no config file. These are the fields `faultline init` writes
# (STARTER in harness/faultline/cli.py) for everything the record does not hold.
STARTER = {"robot": "models/quadruped.xml", "policy": "stand", "duration_s": "5.0",
           "seeds": "{sampler: 0xA13F, sim: 0, policy: 0}", "grace_s": 0.3}


def campaign_yaml(c, markup=True):
    """The published campaign written as a config file. Axes, rules, budget and
    reduction come from the record; the rest is the starter's. The page says so,
    and tests/test_teeter_site.py loads this through the harness's own parser."""
    k = (lambda s: f'<span class="k">{s}</span>') if markup else (lambda s: s)
    cm = (lambda s: f'<span class="c"># {s}</span>') if markup else (lambda s: f"# {s}")
    q = ink.esc if markup else (lambda s: s)
    axes, preds = c["space"], c["report"]["predicates"]
    aw = max(map(len, axes)) + 2
    nw, sw = (max(len(p[key]) for p in preds) + 1 for key in ("name", "signal"))
    out = [f'{k("robot")}: {STARTER["robot"]}', f'{k("policy")}: {STARTER["policy"]}',
           f'{k("duration_s")}: {STARTER["duration_s"]}', "",
           cm("three seeds, never one: a single seed hides which"),
           cm("component caused a divergence on replay"),
           f'{k("seeds")}: {STARTER["seeds"]}', "", f'{k("axes")}:']
    out += [f"  {(name + ':').ljust(aw)}[{lo:g}, {hi:g}]" for name, (lo, hi) in axes.items()]
    out += ["", f'{k("predicates")}:']
    out += [f'  - {{name: {(p["name"] + ",").ljust(nw)} signal: {(p["signal"] + ",").ljust(sw)} '
            f'op: "{q(p["op"])}", threshold: {p["threshold"]}, grace_s: {STARTER["grace_s"]}}}' for p in preds]
    out += ["", f'{k("search")}: {{method: cem, budget: {c["budget"]}}}',
            f'{k("reduce")}: {{enabled: true, max: {c["report"]["reduced"]}}}']
    return "\n".join(out)


def modes_rows(c):
    heads = ("Failure mode", "Count", "Minimal, requested", "First breach")
    rows = []
    for m in c["report"]["modes"]:
        mins = " · ".join(f"{k} {v:g}" for k, v in m["minimal"].items())
        cells = (ink.esc(m["label"]), m["count"], ink.esc(mins), f'{m["first_t"]:.2f} s')
        rows.append("<tr>" + "".join(f'<td data-th="{h}">{v}</td>' for h, v in zip(heads, cells)) + "</tr>")
    return "".join(rows)


# ── values referenced in the prose ───────────────────────────────────────
def wilson(k, n, z=1.96):
    """95% Wilson score interval for k failures in n uniform trials."""
    p, d = k / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return centre - half, centre + half


def site_values(c, s):
    v = ink.values(c, s)
    # only the uniform arm supports a rate; the directed arm's hit rate describes the search
    k, n = sum(c["totals"]["random"]), len(c["totals"]["random"]) * c["budget"]
    lo, hi = wilson(k, n)
    v.update({"n_seeds": len(c["seeds"]), "unif_k": k, "unif_n": n,
              "unif_lo": f"{100 * lo:.1f}", "unif_hi": f"{100 * hi:.1f}",
              "theta_c": f"{math.degrees(bb.THETA):.2f}"})
    return v


def fill(html, vals):
    """Set the text of every element carrying data-v. Values are plain text, so
    an element whose content holds markup is refused rather than overwritten."""
    unknown, done = set(), 0

    def put(m):
        nonlocal done
        tag, attrs, key = m.group(1), m.group(2), m.group(3)
        if key not in vals:
            unknown.add(key)
            return m.group(0)
        done += 1
        return f"<{tag}{attrs}>{ink.esc(vals[key])}</{tag}>"

    html = re.sub(r'<(\w+)(\s[^>]*?\bdata-v="([\w.]+)"[^>]*)>[^<]*</\1>', put, html)
    if unknown:
        sys.exit(f"page asks for values that are not derived: {', '.join(sorted(unknown))}")
    asked = len(re.findall(r'\bdata-v="', html))
    if asked != done:
        sys.exit(f"{asked - done} data-v element(s) hold markup and were not filled")
    return html, done


# ── the social card ──────────────────────────────────────────────────────
def render_og(body):
    """Rasterise the social card at 1200 x 630 with the site's own font files.
    Needs Playwright; CHROMIUM names a browser binary if the bundled one is absent."""
    from playwright.sync_api import sync_playwright

    doc = (f'<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="{(SITE / "css/fonts.css").as_uri()}">'
           f'<style>html,body{{margin:0;background:#0B0B0A}}svg{{display:block}}</style>'
           f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">{body}</svg>')
    tmp = SITE / "assets" / ".og.html"
    tmp.write_text(doc)
    try:
        with sync_playwright() as pw:
            exe = os.environ.get("CHROMIUM")
            browser = pw.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else \
                pw.chromium.launch(args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.goto(tmp.as_uri())
            page.evaluate("document.fonts.ready")
            ok = page.evaluate("document.fonts.check('56px Archivo') && document.fonts.check('17px \"B612 Mono\"')")
            if not ok:
                sys.exit("social card: the site's fonts did not load, refusing to render a fallback face")
            page.screenshot(path=str(SITE / "assets" / "og.png"))
            browser.close()
    finally:
        tmp.unlink(missing_ok=True)


def main():
    import json
    c = json.loads((ROOT / "assets/data/campaign.json").read_text())
    s = json.loads((ROOT / "media/sim.json").read_text())

    # the scatter claims to show every evaluation of the campaign the report came from
    fails = sum(1 for p in c["scatter"]["points"] if p["f"])
    if (len(c["scatter"]["points"]), fails) != (c["budget"], c["report"]["failures_total"]):
        sys.exit(f"scatter holds {len(c['scatter']['points'])} points and {fails} failures; "
                 f"the report records {c['budget']} and {c['report']['failures_total']}")

    vb, lock = bb.lockup()
    pieces = {
        "lockup": bb.inline(vb, lock),
        "lockup-tb": bb.inline(vb, lock),
        "construction": ('<svg class="draw" viewBox="0 0 480 400" role="img" aria-label="Construction of the '
                         'Teeter mark: a 7 by 10 block tipped about its corner P to 34.99 degrees, where its '
                         'centre of mass G sits directly over P. Its upright position is drawn in phantom line, '
                         f'with the arc G travels.">{bb.construction()}</svg>'),
        "coverage": ink.fig_coverage(c),
        "trace": wide_and_narrow(bb.trace_figure(s, c), bb.trace_figure(s, c, pid="hx-trace-n", w=360)),
        "scatter": scatter_figure(c),
        "efficiency": efficiency_figure(c),
        "reduction": wide_and_narrow(bb.reduction_figure(c), bb.reduction_figure(c, pid="hx-red-n", w=360)),
        "mark": bb.inline(f"0 0 {f(bb.MARK_W)} {f(bb.MARK_H)}", bb.mark_body(bb.MARK_OX, bb.MARK_OY)),
        "modes": modes_rows(c),
        "yaml": campaign_yaml(c),
    }
    html = PAGE.read_text()
    missing = [k for k in pieces if f"<!-- gen:{k} -->" not in html]
    if missing:
        sys.exit(f"page has no region for: {', '.join(missing)}")
    bb.inject(PAGE, pieces)

    vals = site_values(c, s)
    html, n = fill(PAGE.read_text(), vals)
    PAGE.write_text(html)

    recorded = c["report"]["modes"][0]["first_t"]
    if abs(float(vals["breach_t"]) - recorded) > 1e-9:
        sys.exit(f"first breach disagrees: captured {vals['breach_t']} s, campaign records {recorded} s")

    print(f"{len(pieces)} regions, {n} values -> {PAGE.relative_to(ROOT)}")
    print(f"  breach {vals['breach_t']} s at {vals['threshold']}° (campaign records {recorded} s)")
    print(f"  uniform: {vals['unif_k']} of {vals['unif_n']}, 95% Wilson {vals['unif_lo']}–{vals['unif_hi']}%"
          f"; directed hit rate {vals['rate_cem']}% (not a failure rate)")
    print(f"  sampled failures {vals['fail_lo']}–{vals['fail_hi']}, reduced to {vals['minimal_push']}")

    if "--og" in sys.argv:
        render_og(bb.social_svg(lock, *map(float, vb.split()[2:])))
        print(f"  social card -> {(SITE / 'assets/og.png').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
