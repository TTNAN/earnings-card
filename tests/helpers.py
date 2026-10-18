import json, os, re, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "earnings-card", "scripts")
FIX = os.path.join(ROOT, "tests", "fixtures")
GOLD = os.path.join(ROOT, "tests", "golden")
TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
HEADLINES = {"en": "Golden test headline", "zh": "金标测试标题"}
sys.path.insert(0, SCRIPTS)


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def opt(name):
    p = os.path.join(FIX, name)
    return load(name) if os.path.exists(p) else None


def render_all(ticker, lang):
    """Render every card for a fixture; return {card: svg}."""
    import render as R
    d = load(f"{ticker}.json")
    t, l = R.THEMES["light"], R.L[lang]
    labels = (opt(f"{ticker}-labels.json") or {}) if lang == "zh" else {}
    g = opt(f"{ticker}-guide-{lang}.json")
    out = {"cover": R.card_cover(d, l, lang, t, HEADLINES[lang]),
           "profit": R.card_profit(d, l, lang, t),
           "trend": R.card_trend(d, l, lang, t),
           "cash": R.card_cash(d, l, lang, t),
           "wide": R.card_wide(d, l, lang, t, HEADLINES[lang])}
    if d.get("segments"):
        out["mix"] = R.card_mix(d, l, lang, t, labels)
    if g:
        out["guide"] = R.card_guide(d, l, lang, t, g)
    return out


def texts(svg):
    """Every visible text in the card, in drawing order."""
    root = ET.fromstring(svg)
    return ["".join(e.itertext()) for e in root.iter() if e.tag.endswith("}text") or e.tag == "text"]


def norm(items):
    # Line wrapping depends on installed fonts, so compare with all whitespace removed.
    return re.sub(r"\s+", "", "".join(items))


def same(a, b):
    """Equal after norm(); a long label cut to "…" (font-dependent) matches its full text."""
    a, b = norm(a), norm(b)
    if a == b:
        return True
    pat = lambda x: "^" + ".*?".join(re.escape(p) for p in x.split("…")) + "$"
    return bool(re.match(pat(a), b) or re.match(pat(b), a))
