#!/usr/bin/env python3
"""Contrast lint for rendered cards: every piece of text and every data mark must stand out from what is
actually painted behind it.

For each <text> the colour behind it is composited from the shapes painted before it (page, gradient page,
translucent boxes, bars...) at three points along the text; for each data mark (render.py tags them
data-mark="data" / "seg") the colour behind its middle (bars) or its vertices (lines). WCAG 2 ratios:

  text            4.5:1   (3:1 when large: >= 24px, or >= 18.66px at weight 700+)
  data marks      3:1     bars and lines that carry a value (data-mark="data")
  segment fills   1.5:1   fills whose value is printed as text too (mix shares, guidance bands; data-mark="seg")

  python3 tools/check_contrast.py              # every style x every card x all ratios x en/zh, + colour overrides
        [--styles dark,bloomberg] [--fixtures NVDA,AAPL] [--ratios 4:5] [--no-variants] [-v]

Exit code 1 when anything fails. tests/test_contrast.py runs the same sweep.
"""
import os, re, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "earnings-card", "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import render as R
from check_layout import _measure_as

NS = "{http://www.w3.org/2000/svg}"
NEED_TEXT, NEED_LARGE, NEED_MARK, NEED_SEG = 4.5, 3.0, 3.0, 1.5

# colour overrides people pick on the site (bg / ink / hi, red-up for Chinese markets): the engine must keep
# the semantic colours readable after any of them
VARIANTS = [
    ("cn", dict(updown="cn")),
    ("light>dark-bg", dict(base="light", bg="#121212", ink="#F2EFE8")),
    ("dark>light-bg", dict(base="dark", bg="#F4F1EA", ink="#151515")),
    ("mono>navy", dict(base="mono", bg="#0B1A33", ink="#FFFFFF", hi="#FFD60A")),
    ("bloomberg>white", dict(base="bloomberg", bg="#FFFFFF")),
    ("keynote>hi-dark", dict(base="keynote", hi="#1D1D1F")),
]


def _rgb(c):
    return tuple(v / 255 for v in R._hex(c))


def _over(top, a, under):
    return tuple(t * a + u * (1 - a) for t, u in zip(top, under))


def _hexs(rgb):
    return "#" + "".join(f"{round(v * 255):02X}" for v in rgb)


def _paint_list(root):
    """Paint-order elements, skipping defs / clipPath contents; gradients by id."""
    grads, out = {}, []

    def walk(e, hidden):
        tag = e.tag.replace(NS, "")
        if tag == "linearGradient":
            grads[e.get("id")] = [(float(s.get("offset")), s.get("stop-color")) for s in e.iter(NS + "stop")]
        hid = hidden or tag in ("defs", "clipPath")
        if not hid and tag in ("rect", "circle", "text", "polyline"):
            out.append(e)
        for ch in e:
            walk(ch, hid)
    walk(root, False)
    return grads, out


def _fill_at(e, px, py, W, H, grads):
    f = e.get("fill")
    if not f or f == "none":
        return None
    m = re.match(r"url\(#(.+)\)", f)
    if m:
        stops = grads.get(m.group(1))
        if not stops:
            return None
        u = max(0, min(1, (px / W + py / H) / 2))   # x1=0 y1=0 x2=1 y2=1 in bounding-box units
        for (o0, c0), (o1, c1) in zip(stops, stops[1:]):
            if o0 <= u <= o1:
                k = (u - o0) / ((o1 - o0) or 1)
                return tuple(a + (b - a) * k for a, b in zip(_rgb(c0), _rgb(c1)))
        return _rgb(stops[-1][1])
    return _rgb(f)


def _contains(e, px, py):
    tag = e.tag.replace(NS, "")
    if tag == "rect":
        x, y = float(e.get("x", 0)), float(e.get("y", 0))
        return x <= px <= x + float(e.get("width")) and y <= py <= y + float(e.get("height"))
    if tag == "circle":
        return (px - float(e.get("cx"))) ** 2 + (py - float(e.get("cy"))) ** 2 <= float(e.get("r")) ** 2
    return False


def _behind(items, upto, px, py, W, H, grads, mark=False):
    col = (1.0, 1.0, 1.0)
    for e in items[:upto]:
        if mark:   # what a mark stands on is an area: not its own drop shadow, a hairline, another series' dot
            if e.get("data-shadow") or e.tag == NS + "circle" or e.get("data-mark"):
                continue
            if e.tag == NS + "rect" and min(float(e.get("width")), float(e.get("height"))) <= 2:
                continue
        if e.tag.replace(NS, "") not in ("rect", "circle") or not _contains(e, px, py):
            continue
        f = _fill_at(e, px, py, W, H, grads)
        if f is None:
            continue
        a = float(e.get("fill-opacity", 1)) * float(e.get("opacity", 1))
        col = _over(f, a, col)
    return _hexs(col)


def problems(svg):
    """[(kind, label, fg, bg, ratio, need)] for everything below its threshold."""
    root = ET.fromstring(svg)
    vb = [float(v) for v in root.get("viewBox").split()]
    W, H = vb[2], vb[3]
    grads, items = _paint_list(root)
    errs = []
    for i, e in enumerate(items):
        tag = e.tag.replace(NS, "")
        if tag == "text":
            s = "".join(e.itertext())
            if not s.strip():
                continue
            fill = e.get("fill")
            if not fill or not fill.startswith("#"):
                continue
            x, y, size = float(e.get("x")), float(e.get("y")), float(e.get("font-size"))
            wt = int(e.get("font-weight", 400))
            w = _measure_as(e.get("font-family"), s, size, wt, float(e.get("letter-spacing", 0)))
            need = NEED_LARGE if size >= 24 or (size >= 18.66 and wt >= 700) else NEED_TEXT
            worst = None
            for fx in (0.1, 0.5, 0.9):
                bg = _behind(items, i, x + w * fx, y - size * 0.35, W, H, grads)
                fg = _hexs(_over(_rgb(fill), float(e.get("fill-opacity", 1)), _rgb(bg)))
                r = R.contrast(fg, bg)
                if worst is None or r < worst[2]:
                    worst = (fg, bg, r)
            if worst[2] < need - 1e-6:
                errs.append(("text", s, worst[0], worst[1], worst[2], need))
        elif e.get("data-mark"):
            need = NEED_MARK if e.get("data-mark") == "data" else NEED_SEG
            if tag == "rect":
                x, y, w, h = (float(e.get(k)) for k in ("x", "y", "width", "height"))
                pts = [(x + w / 2, y + h / 2)]
                fill = e.get("fill")
            else:
                nums = [float(v) for v in re.split(r"[ ,]+", e.get("points").strip())]
                pts = list(zip(nums[::2], nums[1::2]))
                fill = e.get("stroke")
            worst = None
            for px, py in pts:
                bg = _behind(items, i, px, py, W, H, grads, True)
                r = R.contrast(fill, bg)
                if worst is None or r < worst[2]:
                    worst = (fill, bg, r)
            if worst[2] < need - 1e-6:
                errs.append(("mark" if need == NEED_MARK else "seg", tag, worst[0], worst[1], worst[2], need))
    return errs


def styles_to_check(names=None, variants=True):
    """[(name, style dict)]: every built-in style, then the colour-override variants."""
    names = names or [k for k in R.THEMES if k not in ("paper", "ink")]
    out = [(k, R.build_style({"base": k})) for k in names]
    if variants:
        for k in names:
            out.append((f"{k}+cn", R.recolor(R.build_style({"base": k}), updown="cn")))
        for vname, v in VARIANTS[1:]:
            v = dict(v)
            base = v.pop("base")
            if base in names:
                out.append((vname, R.recolor(R.build_style({"base": base}), v.get("bg"), v.get("ink"), v.get("hi"))))
    return out


def sweep(fixtures=None, styles=None, ratios=None, variants=True, langs=("en", "zh"), verbose=False):
    """Render and check; returns (cards checked, [failure lines])."""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from helpers import load, opt
    fixtures = fixtures or ["NVDA", "AAPL", "AMZN", "META", "TSLA", "NVDA-annual", "JPM"]
    ratios = ratios or list(R.RATIOS)
    n, fails = 0, []
    for fx in fixtures:
        if not os.path.exists(os.path.join(ROOT, "tests", "fixtures", fx + ".json")):
            continue
        d = load(fx + ".json")
        tk = fx.split("-")[0]
        for lang in langs:
            g = opt(f"{tk}-guide-{lang}.json")
            labels = (opt(f"{tk}-labels.json") or {}) if lang == "zh" else {}
            head = "Revenue doubled, margins held" if lang == "en" else "营收同比翻倍，毛利率稳在 75%"
            for sname, t in styles_to_check(styles, variants):
                for ratio in ratios:
                    for name, svg in R.render_cards(d, lang, dict(t, handle="@handle"), R.DEFAULT_CARDS + R.EXTRA_CARDS,
                                                    ratio, head, g, labels):
                        n += 1
                        for kind, what, fg, bg, r, need in problems(svg):
                            fails.append(f"{sname:16} {name:7} {kind:4} {fg} on {bg} {r:4.2f} < {need}  {what[:40]!r}"
                                         + (f"  [{fx} {lang} {ratio}]" if verbose else ""))
    return n, fails


def _arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    sp = lambda v: v.split(",") if v else None
    n, fails = sweep(sp(_arg("--fixtures")), sp(_arg("--styles")), sp(_arg("--ratios")),
                     "--no-variants" not in sys.argv, verbose="-v" in sys.argv)
    from collections import Counter
    if "-v" in sys.argv:
        for f in fails:
            print(f)
    else:   # one line per distinct problem, with how often it occurred
        for f, k in sorted(Counter(fails).items(), key=lambda kv: kv[0]):
            print(f"{k:5}x  {f}")
    print(f"{n} cards checked, {len(fails)} contrast failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
