#!/usr/bin/env python3
"""Layout lint for rendered cards: every text box must sit inside the canvas and no two may overlap.

Uses render.measure() with the style that rendered the card, so run it with the real fonts installed
(on a machine without them widths are estimates and the check is only approximate).

  python3 tools/check_layout.py            # all fixtures x ratios x styles x langs, prints problems
  python3 tools/check_layout.py --data     # every ticker in docs/data, every stored period, every card
        [--styles light,terminal,salmon] [--latest] [--tickers NVDA,AAPL] [--shard 0/2]

Layout only depends on a style's font (colours, corners and outlines don't move text), so the default
--data styles are one per font family: light (sans), terminal (mono), salmon (serif); that covers all 12.
"""
import os, re, sys, itertools
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "earnings-card", "scripts"))
import render as R

NS = "{http://www.w3.org/2000/svg}"


def boxes(svg):
    root = ET.fromstring(svg)
    W, H = float(root.get("width")), float(root.get("height"))
    vb = [float(v) for v in root.get("viewBox").split()]
    out = []
    for e in root.iter(NS + "text"):
        s = "".join(e.itertext())
        if not s.strip():
            continue
        x, y, size = float(e.get("x")), float(e.get("y")), float(e.get("font-size"))
        w = R.measure(s, size, int(e.get("font-weight", 400)), float(e.get("letter-spacing", 0)))
        out.append((s, x, y - 0.74 * size, x + w, y + 0.2 * size))
    return vb[2], vb[3], out


def problems(svg, margin=24, slack=2):
    W, H, bs = boxes(svg)
    errs = []
    for s, x0, y0, x1, y1 in bs:
        if x0 < margin - 8 or x1 > W - margin + 4 or y0 < 0 or y1 > H:
            errs.append(f"out of bounds: {s!r} x {x0:.0f}..{x1:.0f} (W {W:.0f}) y {y0:.0f}..{y1:.0f} (H {H:.0f})")
    for a, b in itertools.combinations(bs, 2):
        ox = min(a[3], b[3]) - max(a[1], b[1])
        oy = min(a[4], b[4]) - max(a[2], b[2])
        if ox > slack and oy > slack:
            errs.append(f"overlap: {a[0]!r} / {b[0]!r} ({ox:.0f}x{oy:.0f}px)")
    return errs


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main_data():
    """Every precomputed ticker in docs/data, every stored period (or --latest), all ratios, both languages, all cards."""
    import glob, json
    ddir = os.path.join(ROOT, "docs", "data")
    common = json.load(open(os.path.join(ddir, "labels-zh.json"), encoding="utf-8"))
    styles = _arg("--styles", "light,terminal,salmon").split(",")
    only = set(_arg("--tickers", "").split(",")) - {""}
    shard = _arg("--shard")
    k, m = (int(v) for v in shard.split("/")) if shard else (0, 1)
    cards = R.DEFAULT_CARDS + R.EXTRA_CARDS
    n = bad = 0
    files = [f for f in sorted(glob.glob(os.path.join(ddir, "*.json")))
             if os.path.basename(f)[:-5].replace("-", "").isupper()]
    for fi, f in enumerate(files):
        tk = os.path.basename(f)[:-5]
        if (only and tk not in only) or fi % m != k:
            continue
        rec = json.load(open(f, encoding="utf-8"))
        lab = dict(common)
        lp = os.path.join(ddir, "labels", tk + ".json")
        if os.path.exists(lp):
            lab.update(json.load(open(lp, encoding="utf-8")))
        for period in ("quarter", "annual"):
            block = rec.get(period)
            if not block:
                continue
            ends = [p["period_end"] for p in block.get("periods", [block])]
            if "--latest" in sys.argv:
                ends = ends[-1:]
            for end in ends:
                d = R.period_record(block, end)
                for lang in ("en", "zh"):
                    gp = os.path.join(ddir, "guide", f"{tk}-guide-{lang}.json")
                    g = json.load(open(gp, encoding="utf-8")) if os.path.exists(gp) and period == "quarter" else None
                    if g and g["prior"]["period"] != d["fiscal_label"]:
                        g = None
                    for ratio in R.RATIOS:
                        for st in styles:
                            t = R.build_style({"base": st, "handle": "@handle"})
                            head = "Revenue up, margins steady" if lang == "en" else "营收增长，利润率稳住"
                            for name, svg in R.render_cards(d, lang, t, cards, ratio, head, g, lab if lang == "zh" else {}):
                                n += 1
                                for e in problems(svg):
                                    bad += 1
                                    print(f"{tk} {period} {d.get('fiscal_label')} {lang} {ratio} {st} {name}: {e}", flush=True)
    print(f"{n} cards checked, {bad} problems")
    return 1 if bad else 0


def main():
    if "--data" in sys.argv:
        return main_data()
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from helpers import load, opt
    fixtures = sys.argv[1:] or ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
                                "NVDA-annual", "AAPL-annual", "JPM", "JPM-annual"]
    styles = [k for k in R.THEMES if k not in ("paper", "ink")]
    n = bad = 0
    for fx in fixtures:
        if not os.path.exists(os.path.join(ROOT, "tests", "fixtures", fx + ".json")):
            continue
        d = load(fx + ".json")
        tk = fx.split("-")[0]
        for lang in ("en", "zh"):
            g = opt(f"{tk}-guide-{lang}.json")
            labels = (opt(f"{tk}-labels.json") or {}) if lang == "zh" else {}
            for ratio in R.RATIOS:
                for st in styles:
                    t = R.build_style({"base": st, "handle": "@a_long_handle"})
                    for head in ("A fairly long headline for the cover card" if lang == "en" else "营收同比翻倍，毛利率稳在七成五", ""):
                        for name, svg in R.render_cards(d, lang, t, R.DEFAULT_CARDS + R.EXTRA_CARDS, ratio, head, g, labels):
                            if not head and name not in ("cover", "wide", "poster", "post"):
                                continue
                            n += 1
                            for e in problems(svg):
                                bad += 1
                                print(f"{fx} {lang} {ratio} {st} {name} {'H' if head else '-'}: {e}")
    print(f"{n} cards checked, {bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
