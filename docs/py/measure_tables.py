"""Text widths for render.py from per-font width tables (used by the web generator's worker).

The browser renders in a Web Worker, which can't measure with the page's web fonts. The page measures
every character it expects at 100px with canvas measureText, per (CSS font family string, weight), and
sends the tables over; this module sums them. One representative CJK width covers any other char >= U+2E80.

  tables JSON: {"<family>|<weight>": {"chars": {"A": 68.1, ...}, "cjk": 100.0, "other": 55.0}}
"""
import json
import render

_T = {}


def families():
    """Every CSS font-family string render.py can pass to the measurer for the built-in styles."""
    fams = {render.SANS, render.SANS_SC}
    for s in render.FONT_SETS.values():
        fams.update(s[:2])
    for t in render.THEMES.values():
        fams.update(v for k, v in t.items() if k in ("font", "cjk_font"))
    return sorted(fams)


def set_tables(tables_json):
    """Install new tables (e.g. after web fonts finished loading) and clear render.py's width cache."""
    global _T
    t = {}
    for k, v in json.loads(tables_json).items():
        fam, w = k.rsplit("|", 1)
        t.setdefault(fam, {})[int(w)] = v
    _T = t
    render.set_measurer(measure)


def _table(fam, weight):
    ws = _T.get(fam)
    if not ws:
        return None
    if weight in ws:
        return ws[weight]
    return ws[min(ws, key=lambda w: (abs(w - weight), w))]   # nearest weight; ties go lighter


def measure(text, fam, size, weight):
    t = _table(fam, int(weight))
    if t is None:   # family the page didn't measure: same rough estimate render.py uses without fonts
        return sum(size if ord(c) > 0x2E80 else size * 0.6 for c in text)
    chars, cjk, other = t["chars"], t["cjk"], t.get("other", 55.0)
    return sum(chars.get(c, cjk if ord(c) >= 0x2E80 else other) for c in text) * size / 100.0
