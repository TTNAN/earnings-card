#!/usr/bin/env python3
"""Render a set of earnings cards (SVG + HTML, optional PNG) from fetch_sec.py JSON.

Usage:
  python3 render.py data.json --out ./NVDA [--lang zh|en] [--headline "一句话结论"]
                    [--style light|dark|mono|terminal|salmon|pop|bloomberg|keynote|neon|vintage|morandi|glass|my-style.json]
                    [--ratio 4:5|1:1|9:16|16:9] [--cards cover,mix,profit,trend,cash,guide,wide,poster,post,income,yoy,score]
                    [--period-end YYYY-MM-DD | --fy 2026 --fq 2]   (data from tools/build_data.py, schema v2)
                    [--guidance guidance.json] [--labels labels.json] [--png]

Works for quarterly data (default) and annual data (fetch_sec.py --period annual); the labels
switch to fiscal years automatically.

Cards (1080x1350 at the default 4:5 ratio; 1:1 = 1080x1080, 9:16 = 1080x1920, 16:9 = 1920x1080):
  cover   headline, revenue, revenue bars, 4 key metrics (at 16:9 it uses the landscape layout)
  mix     revenue by business and by region (skipped when the filing has no breakdown)
  profit  waterfall: how every dollar of revenue becomes net income
  trend   gross / operating / net margin lines + net income bars
  cash    operating cash flow, capex, free cash flow, buybacks, dividends, cash pile
  guide   next-quarter outlook and last outlook vs actual (only with --guidance, quarterly only)
  wide    1600x900 landscape cover for X / slides (dropped at 16:9, where the cover already is one)
Extra templates (not in the default set; ask for them with --cards):
  poster  one big number: revenue and its YoY change, nothing else
  post    looks like a social-media post (avatar, handle, a summary of the period, a small chart)
  income  income statement from revenue to EPS, with year-ago figures and YoY
  yoy     this period next to the same period last year, six metrics with arrows
  score   scorecard: actual vs management's last outlook (with --guidance), otherwise vs the previous
          quarter / year. Never vs analyst consensus, which this data does not have; the card says so.

Library use (the web app runs this same file in the browser through Pyodide):
  render_cards(data, lang, style, cards, ratio, headline, guidance, labels) -> [(name, svg)]
  set_measurer(fn)  # fn(text, css_font_family, size, weight) -> width in px; default measures with PIL
"""
import re, json, sys, html, argparse, os, glob

SANS = "Inter, 'Noto Sans SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
SANS_SC = "'Noto Sans SC', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
SERIF = "'Source Serif 4', 'Noto Serif SC', 'Songti SC', 'STSong', Georgia, serif"
SERIF_SC = "'Noto Serif SC', 'Songti SC', 'STSong', 'SimSun', serif"
MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, 'Noto Sans SC', monospace"
# font files used only to measure text width (PIL); browsers use the CSS families above
PIL_SANS = {"bold": ["Inter-ExtraBold*", "Inter-Bold*"], "reg": ["Inter-Medium*", "Inter-Regular*"]}
PIL_SERIF = {"bold": ["SourceSerif4-Black*", "SourceSerif4-Bold*"], "reg": ["SourceSerif4-Regular*"]}
PIL_MONO = {"bold": ["JetBrainsMono-ExtraBold*", "JetBrainsMono-Bold*"], "reg": ["JetBrainsMono-Regular*"]}
PIL_SANS_SC = {"bold": ["NotoSansSC-Bold*", "NotoSansCJK*Bold*", "PingFang*"], "reg": ["NotoSansSC-Regular*", "NotoSansCJK*Regular*", "PingFang*"]}
PIL_SERIF_SC = {"bold": ["NotoSerifSC-Bold*", "NotoSerifCJK*Bold*", "Songti*"], "reg": ["NotoSerifSC-Regular*", "NotoSerifCJK*Regular*", "Songti*"]}

# Built-in styles. Every key can be overridden with --style my-style.json (see styles/README in the skill).
#   bg ink sub faint bar card: page, text, secondary text, hairlines, chart bars, metric boxes
#   up down: good / bad numbers;  a1 a2 a3: line-chart series;  hi: highlighted bar (latest quarter)
#   palette: segment colors;  round: corner radius multiplier (0 = square);  stroke: box outline width
THEMES = {
    "light": dict(label="Paper · 杂志米白", display="serif", bg="#F4F1EA", ink="#151515", sub="#6F6A60", faint="#DDD7CB", bar="#CFC8BA",
                  up="#1E7A4C", down="#B5403A", card="#FBF9F4", a1="#151515", a2="#8C6A3F", a3="#9C978C",
                  palette=["#151515", "#8C6A3F", "#B9A27E", "#6F6A60", "#CFC8BA", "#E3DDD1", "#A8A296", "#EFEAE0"]),
    "dark": dict(label="Ink · 墨黑", bg="#121212", ink="#F2EFE8", sub="#9A958B", faint="#2E2C29", bar="#3A3733",
                 up="#5BC48A", down="#E5776F", card="#1A1A19", a1="#F2EFE8", a2="#D9A65E", a3="#77736B", band="#77736B",
                 palette=["#F2EFE8", "#D9A65E", "#9C7C4E", "#9A958B", "#5A5650", "#3A3733", "#77736B", "#2E2C29"]),
    "mono": dict(label="Swiss · 极简黑白", bg="#FFFFFF", ink="#000000", sub="#6B6B6B", faint="#E4E4E4", bar="#D6D6D6",
                 up="#00873C", down="#E10600", card="#FFFFFF", a1="#000000", a2="#E10600", a3="#9A9A9A", hi="#000000",
                 round=0, stroke=2, card_stroke="#000000",
                 palette=["#000000", "#E10600", "#6B6B6B", "#A8A8A8", "#CFCFCF", "#E6E6E6", "#555555", "#F2F2F2"]),
    "terminal": dict(label="Terminal · 终端", bg="#0A0A0A", ink="#FFB000", sub="#9C8A62", faint="#2B261C", bar="#3D3424",
                     up="#3BE08A", down="#FF5A4E", card="#12100C", a1="#FFB000", a2="#33C7FF", a3="#9C8A62", band="#5C4D30",
                     round=0, stroke=1.5, font=MONO, cjk_font=SANS_SC, pil=PIL_MONO,
                     palette=["#FFB000", "#33C7FF", "#3BE08A", "#C77DFF", "#9C8A62", "#5C4D30", "#FF5A4E", "#2B261C"]),
    "salmon": dict(label="Salmon · 财经报纸", bg="#FFF1E5", ink="#33302E", sub="#66605C", faint="#E6D9CE", bar="#E3CDBA",
                   up="#0D7680", down="#CC0000", card="#FFF8F2", a1="#0D7680", a2="#990F3D", a3="#8F8580", hi="#0D7680",
                   round=0.3, stroke=1, font=SERIF, cjk_font=SERIF_SC, pil=PIL_SERIF, pil_cjk=PIL_SERIF_SC,
                   palette=["#0D7680", "#990F3D", "#593380", "#FF8833", "#96CC28", "#B3A9A0", "#66605C", "#E6D9CE"]),
    "pop": dict(label="Pop · 小红书色块", bg="#FFF5F3", ink="#1B1B1B", sub="#7A6E6C", faint="#FFDCD6", bar="#FFC9C1",
                up="#11A35B", down="#FF2442", card="#FFFFFF", a1="#FF2442", a2="#D46A00", a3="#7A6E6C", hi="#FF2442",
                round=1.6, stroke=0, band="#FFC9C1",
                palette=["#FF2442", "#D46A00", "#FFC300", "#3D7BFF", "#11A35B", "#B25CFF", "#7A6E6C", "#FFDCD6"]),
    # bloomberg: terminal-screen orange on black;  keynote: launch-event black, big type, quiet greys
    "bloomberg": dict(label="Bloomberg · 彭博橙", bg="#000000", ink="#FB8B1E", sub="#BDBDBD", faint="#2A2A2A", bar="#4A4A4A",
                      up="#4AF6C3", down="#FF433D", card="#0E0E0E", a1="#FB8B1E", a2="#4AA3FF", a3="#BDBDBD", hi="#FB8B1E",
                      band="#6B4A22", round=0, stroke=1.5, card_stroke="#3A2A14", font=MONO, cjk_font=SANS_SC, pil=PIL_MONO,
                      palette=["#FB8B1E", "#4AA3FF", "#4AF6C3", "#FFFFFF", "#BDBDBD", "#7A5A30", "#FF433D", "#2A2A2A"]),
    "keynote": dict(label="Keynote · 苹果发布会", bg="#000000", ink="#F5F5F7", sub="#86868B", faint="#1D1D1F", bar="#2C2C2E",
                    up="#30D158", down="#FF453A", card="#111113", a1="#F5F5F7", a2="#2997FF", a3="#86868B", hi="#2997FF",
                    band="#3A3A3C", round=1.4, stroke=0,
                    palette=["#2997FF", "#F5F5F7", "#BF5AF2", "#30D158", "#FF9F0A", "#86868B", "#3A3A3C", "#1D1D1F"]),
    # neon: purple-black with cyan / magenta accents (flat colours and thin outlines, no blur filters)
    "neon": dict(label="Neon · 赛博霓虹", bg="#0D0A1A", ink="#EDE9FF", sub="#9A90C8", faint="#2A2347", bar="#3A2F66",
                 up="#22E4FF", down="#FF3DCB", card="#141029", a1="#22E4FF", a2="#FF3DCB", a3="#9A90C8", hi="#FF3DCB",
                 band="#5A2F7A", round=1, stroke=1.5, card_stroke="#22E4FF", card_stroke_opacity=0.55,
                 palette=["#22E4FF", "#FF3DCB", "#B36BFF", "#FFE45C", "#4DFFA6", "#9A90C8", "#3A2F66", "#2A2347"]),
    "vintage": dict(label="Vintage · 复古报纸", bg="#EFE4C8", ink="#2B2118", sub="#6B5B47", faint="#D6C7A3", bar="#CBB88F",
                    up="#3F6B3A", down="#9E2B1F", card="#F5ECD5", a1="#2B2118", a2="#9E2B1F", a3="#8C7A5E", hi="#2B2118",
                    band="#BFA87A", round=0, stroke=1.2, card_stroke="#2B2118", font=SERIF, cjk_font=SERIF_SC, pil=PIL_SERIF,
                    pil_cjk=PIL_SERIF_SC,
                    palette=["#2B2118", "#9E2B1F", "#6B5B47", "#A88B5A", "#CBB88F", "#3F6B3A", "#8C7A5E", "#E3D6B6"]),
    # morandi: soft greyed dusty colours
    "morandi": dict(label="Morandi · 莫兰迪", bg="#E9E4DE", ink="#4A4643", sub="#6B655F", faint="#D6CFC7", bar="#C9C0B6",
                    up="#55745E", down="#99605A", card="#F2EEE9", a1="#6E7F8D", a2="#8E7360", a3="#9AA597", hi="#6A7891",
                    band="#C2B8C9", round=1.2, stroke=0,
                    palette=["#6E7F8D", "#B59A85", "#9AA597", "#C2A9A1", "#A69CAC", "#D4C6B5", "#8A837D", "#E3DCD3"]),
    # glass: soft gradient page (SVG linearGradient) with translucent white cards
    "glass": dict(label="Glass · 毛玻璃渐变", bg="#D8CCF0", bg_grad=["#B8C8F8", "#E3C8EE", "#F8DCCB"], ink="#1F2240",
                  sub="#4A4A68", faint="#FFFFFF", bar="#FFFFFF", up="#156B46", down="#A8304A", card="#FFFFFF",
                  card_opacity=0.42, a1="#1F2240", a2="#6B4EFF", a3="#8A86A8", hi="#6B4EFF", band="#B9A8F0",
                  round=1.6, stroke=1.2, card_stroke="#FFFFFF", card_stroke_opacity=0.8,
                  palette=["#6B4EFF", "#1F2240", "#E0699B", "#4AA3C8", "#F2A65A", "#8A86A8", "#FFFFFF", "#C9C2E8"]),
}
THEMES["paper"], THEMES["ink"] = THEMES["light"], THEMES["dark"]   # friendlier aliases
FONT, CJK_FONT, _STYLE = SANS, SANS_SC, {}
_PIL_OVR = None   # (pil, pil_cjk) while display text is drawn


FONT_SETS = {"sans": (SANS, SANS_SC, PIL_SANS, PIL_SANS_SC), "serif": (SERIF, SERIF_SC, PIL_SERIF, PIL_SERIF_SC),
             "mono": (MONO, SANS_SC, PIL_MONO, PIL_SANS_SC)}
RATIOS = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "16:9": (1920, 1080)}
DEFAULT_CARDS = ["cover", "mix", "profit", "trend", "cash", "guide", "wide"]


def resolve_style(name_or_path):
    """A built-in style name, or a JSON file: {"base": "light", "bg": "#...", "handle": "@me", "avatar": "me.png", ...}."""
    if name_or_path in THEMES:
        return dict(THEMES[name_or_path])
    with open(name_or_path, encoding="utf-8") as f:
        custom = json.load(f)
    return build_style(custom, os.path.dirname(os.path.abspath(name_or_path)))


def build_style(custom, base_dir=None):
    """Same as a style JSON file, from a dict. A relative avatar path is read from base_dir."""
    custom = dict(custom)
    t = dict(THEMES[custom.pop("base", "light")])
    if custom.get("font") in FONT_SETS:   # an explicit font replaces the style's display font too
        t["font"], t["cjk_font"], t["pil"], t["pil_cjk"] = FONT_SETS[custom.pop("font")]
        t.pop("display", None)
    elif "font" in custom and custom["font"] in (None, "", "auto"):
        custom.pop("font")
    av = custom.get("avatar")
    if av and not av.startswith("data:"):
        import base64, mimetypes
        path = av if os.path.isabs(av) else os.path.join(base_dir or os.getcwd(), av)
        mime = mimetypes.guess_type(path)[0] or "image/png"
        custom["avatar"] = f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()
    t.update(custom)
    return t


def _hex(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, w):
    """Blend colour a toward colour b by w (0..1)."""
    x, y = _hex(a), _hex(b)
    return "#" + "".join(f"{round(p + (q - p) * w):02X}" for p, q in zip(x, y))


def _lum(c):
    out = []
    for v in _hex(c):
        v /= 255
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    """WCAG contrast ratio of two colours (1..21)."""
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def ensure_contrast(fg, bg, need=4.5, toward=None):
    """fg, moved step by step toward `toward` (default black or white, whichever is farther from bg)
    until it reaches `need` against bg. Returns fg unchanged when it already passes."""
    if contrast(fg, bg) >= need:
        return fg
    toward = toward or ("#000000" if _lum(bg) > 0.18 else "#FFFFFF")
    for i in range(1, 21):
        c = _mix(fg, toward, i / 20)
        if contrast(c, bg) >= need:
            return c
    return toward


def recolor(t, bg=None, ink=None, hi=None, a2=None, updown=None):
    """Swap a style's page / text / highlight colours and re-derive the tones that depend on them.

    a2: second accent (operating-margin line, cost bars, 2nd segment colour).
    updown="cn": red for up, green for down (the convention on Chinese markets)."""
    t = dict(t)
    if bg or ink:
        if bg:   # a custom page colour replaces a gradient page
            t.pop("bg_grad", None)
        bg, ink = bg or t["bg"], ink or t["ink"]
        light = sum(_hex(bg)) > 382
        t.update(bg=bg, ink=ink, sub=ensure_contrast(_mix(ink, bg, 0.45), bg, 4.5, ink), faint=_mix(ink, bg, 0.86), bar=_mix(ink, bg, 0.76),
                 card=_mix(bg, "#FFFFFF", 0.5) if light else _mix(bg, ink, 0.05), a1=ink, a3=_mix(ink, bg, 0.5),
                 band=_mix(ink, bg, 0.62))
        if t.get("card_stroke"):
            t["card_stroke"] = ink
        pal = list(t.get("palette") or [])
        t["palette"] = [ink] + pal[1:] if pal else pal
    if hi:
        t["hi"], t["a2"] = hi, hi
        pal = list(t.get("palette") or [t["ink"]])
        t["palette"] = pal[:1] + [hi] + pal[2:]
    if a2:
        t["a2"] = a2
        pal = list(t.get("palette") or [t["ink"], t.get("hi", t["ink"])])
        t["palette"] = pal[:2] + [a2] + pal[3:] if len(pal) >= 2 else pal + [a2]
    if updown == "cn":
        t["up"], t["down"] = t["down"], t["up"]
    return t


def apply_style(t):
    global FONT, CJK_FONT, _STYLE
    if t is not _STYLE:
        FONT, CJK_FONT = t.get("font", SANS), t.get("cjk_font", SANS_SC)
        _STYLE = t
        _FONTS.clear()


L = {
    "zh": dict(rev="营收", gm="毛利率", om="营业利润率", nm="净利率", ni="净利润", eps="稀释每股收益", yoy="同比",
               ended="截至", pts="个百分点", trend="近 {n} 个季度营收（亿美元）",
               note="数据来源 SEC EDGAR · 不构成投资建议", filed="披露",
               profit_t="营收是怎么变成利润的", cost="营业成本", gp="毛利", rnd="研发", sga="销售及管理",
               other_opex="其他经营费用", oi="营业利润", tax="所得税", other="其他收支", of_rev="占营收",
               trend_t="{n} 个季度，利润率怎么走", mix_t="钱从哪里来", guide_t="管理层怎么看下季度", next_g="下季指引", kept="上季指引兑现了吗",
               vs_now="较本季", beat="超出指引上限", inline="落在指引区间内", miss="低于指引下限", actual="实际",
               g_src="指引来自公司财报新闻稿（8-K）", by_product="按业务", by_segment="按分部", by_geo="按地区",
               share="占比", other_seg="其他", margins="利润率", ni_bars="净利润（亿美元）",
               cash_t="赚到的钱去了哪", ocf="经营现金流", capex="资本开支", fcf="自由现金流",
               buyback="回购", div="分红", returned="回馈股东", cashpile="现金及短期投资", cashonly="现金及等价物", capex_ocf="资本开支 / 经营现金流", fcf_bars="自由现金流（亿美元）",
               fcf_note="自由现金流 = 经营现金流 − 资本开支", n_per="个季度", cur="本季", all_costs="成本、费用及税"),
    "en": dict(rev="Revenue", gm="Gross margin", om="Operating margin", nm="Net margin", ni="Net income", eps="Diluted EPS",
               yoy="YoY", ended="Quarter ended", pts="pts", trend="Revenue, last {n} quarters ($B)",
               note="Data: SEC EDGAR · Not investment advice", filed="filed",
               profit_t="From revenue to profit", cost="Cost of revenue", gp="Gross profit", rnd="R&D", sga="SG&A",
               other_opex="Other operating costs", oi="Operating income", tax="Income tax", other="Other income", of_rev="of revenue",
               trend_t="{n} quarters of margins", mix_t="Where the money comes from", guide_t="What management expects next", next_g="Next-quarter outlook",
               kept="Did they hit last quarter's outlook?", vs_now="vs this qtr", beat="Above the range", inline="Within the range",
               miss="Below the range", actual="Actual", g_src="Outlook from the company's earnings release (8-K)", by_product="By business",
               by_segment="By segment", by_geo="By region", share="share", other_seg="Other", margins="Margins", ni_bars="Net income ($B)",
               cash_t="Where the cash went", ocf="Operating cash flow", capex="Capex", fcf="Free cash flow",
               buyback="Buybacks", div="Dividends", returned="Returned to shareholders", cashpile="Cash & short-term investments", cashonly="Cash & equivalents", capex_ocf="Capex / operating cash flow",
               fcf_bars="Free cash flow ($B)", fcf_note="Free cash flow = operating cash flow − capex", n_per="quarters",
               cur="This quarter", all_costs="Costs, expenses & tax"),
}
# Full-year (10-K) cards: only the words that say "quarter" change. {n} = number of years in the trend.
L_ANNUAL = {
    "zh": dict(ended="财年截至", trend="近 {n} 个财年营收（亿美元）", trend_t="{n} 个财年，利润率怎么走", n_per="个财年", cur="本财年"),
    "en": dict(ended="Fiscal year ended", trend="Revenue, last {n} fiscal years ($B)", trend_t="{n} years of margins",
               n_per="years", cur="This year"),
}


def labels_for(lang, period=None):
    l = dict(L[lang])
    if period == "annual":
        l.update(L_ANNUAL[lang])
    return l


TREND_LEN = {"quarter": 8, "annual": 5}


def period_record(block, period_end=None, fy=None, fq=None):
    """One period's full card data (the fetch_sec.py schema) from a docs/data block {series, periods}.

    period_end (YYYY-MM-DD) or fy (+ fq for quarters) picks the period; default is the latest.
    A plain fetch_sec.py record (it already has a "trend") is returned as is. None if no period matches."""
    if "periods" not in block:
        return block
    ps = block["periods"]
    if period_end:
        hit = [p for p in ps if p["period_end"] == period_end]
    elif fy:
        want = f"FY{int(fy)}" + ("" if block.get("period") == "annual" else f" Q{int(fq or 4)}")
        hit = [p for p in ps if p.get("fiscal_label") == want]
    else:
        hit = ps[-1:]
    if not hit:
        return None
    p = hit[-1]
    d = {k: v for k, v in block.items() if k not in ("series", "periods")}
    d.update(p)
    n = TREND_LEN.get(block.get("period"), 8)
    d["trend"] = [q for q in block["series"] if q["end"] <= p["period_end"]][-n:]
    d["source"] = f'SEC EDGAR · {p["form"]} filed {p["filed"]}'
    return d


def is_annual(d):
    return d.get("period") == "annual"


def plabel(q):
    """Bar label for a trend point: 25.07 for quarters, FY25 for fiscal years."""
    return q.get("label") or qlabel(q["end"])


# ---------- text helpers ----------
def esc(s):
    return html.escape(str(s))


def _runs(s):
    out, cur, cjk = [], "", None
    for ch in s:
        c = ord(ch) > 0x2E80
        if cjk is None or c == cjk or ch == " ":
            cur += ch
            cjk = c if cjk is None else cjk
        else:
            out.append((cur, cjk))
            cur, cjk = ch, c
    if cur:
        out.append((cur, cjk))
    return out


_FONTS = {}


def _pil_font(cjk, bold, size):
    if _PIL_OVR:
        src = _PIL_OVR[1] if cjk else _PIL_OVR[0]
    else:
        src = _STYLE.get("pil_cjk", PIL_SANS_SC) if cjk else _STYLE.get("pil", PIL_SANS)
    key = (cjk, bold, size, src["bold" if bold else "reg"][0])
    if key not in _FONTS:
        f = None
        try:
            from PIL import ImageFont
            pats = src["bold" if bold else "reg"]
            dirs = [os.path.expanduser("~/.fonts"), os.path.expanduser("~/Library/Fonts"), "/usr/share/fonts",
                    "/Library/Fonts", "/System/Library/Fonts"]
            for d in dirs:
                for pat in pats:
                    hit = glob.glob(os.path.join(d, "**", pat), recursive=True)
                    if hit:
                        f = ImageFont.truetype(hit[0], size)
                        break
                if f:
                    break
        except Exception:
            f = None
        _FONTS[key] = f
    return _FONTS[key]


_MEASURER, _MCACHE = None, {}


class display_font:
    """with display_font(): headline / title text in the style's display face (THEMES[...]["display"],
    a FONT_SETS key, e.g. serif headlines on the magazine style); body text keeps the style's font."""
    def __enter__(self):
        global FONT, CJK_FONT, _PIL_OVR
        self.saved = FONT, CJK_FONT, _PIL_OVR
        fs = FONT_SETS.get(_STYLE.get("display") or "")
        if fs:
            FONT, CJK_FONT, _PIL_OVR = fs[0], fs[1], (fs[2], fs[3])
        return self

    def __exit__(self, *a):
        global FONT, CJK_FONT, _PIL_OVR
        FONT, CJK_FONT, _PIL_OVR = self.saved


def set_measurer(fn=None):
    """Plug in another text-width function: fn(text, css_font_family, size, weight) -> width in px.

    The web app passes the browser's canvas measureText, so widths match the web fonts on screen.
    None restores the default (PIL with the font files in ~/.fonts, or a rough estimate)."""
    global _MEASURER
    _MEASURER = fn
    _MCACHE.clear()


def measure(s, size, weight=400, ls=0):
    w = 0
    for r, c in _runs(str(s)):
        if _MEASURER is not None:
            key = (r, CJK_FONT if c else FONT, size, weight)
            if key not in _MCACHE:
                _MCACHE[key] = float(_MEASURER(r, key[1], size, weight))
            w += _MCACHE[key]
        else:
            f = _pil_font(c, weight >= 600, size)
            w += f.getlength(r) if f else sum(size if ord(ch) > 0x2E80 else size * 0.6 for ch in r)
        w += ls * len(r)
    return w


def clip(s, max_w, size, weight=400, ls=0):
    """s, cut with an ellipsis if it is wider than max_w."""
    if measure(s, size, weight, ls) <= max_w:
        return s
    while len(s) > 2 and measure(s + "…", size, weight, ls) > max_w:
        s = s[:-1]
    return s.rstrip(" ,.") + "…"


def fit(s, max_w, size, weight=400, ls=0, floor=14):
    """Largest font size <= size at which s fits in max_w."""
    while size > floor and measure(s, size, weight, ls) > max_w:
        size -= 1
    return size


def text(x, y, s, size, fill, weight=400, anchor="start", ls=0):
    # Anchors are resolved here: some SVG rasterizers misplace multi-tspan text with text-anchor.
    if anchor != "start":
        wd = measure(s, size, weight, ls)
        x = round(x - wd if anchor == "end" else x - wd / 2, 1)
    body = "".join(f'<tspan font-family="{CJK_FONT if c else FONT}">{esc(r)}</tspan>' for r, c in _runs(str(s)))
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" letter-spacing="{ls}" xml:space="preserve">{body}</text>')


def wrap(s, max_w, size, weight, max_lines=2):
    lines, cur = [], ""
    # break on spaces for Latin text, anywhere for CJK
    for ch in re.findall(r"[A-Za-z0-9$%.,;:()'\-–+~]+ ?|.", s):
        if measure(cur + ch, size, weight) > max_w and cur:
            lines.append(cur)
            cur = ""
        cur += ch
    if cur:
        lines.append(cur)
    return lines[:max_lines]


# ---------- number helpers ----------
def money(v, lang, digits=1):
    if v is None:
        return "—"
    neg, v = v < 0, abs(v)
    if lang == "zh":
        if v >= 1e12:
            s = f"${v/1e12:.2f}万亿"
        elif v >= 1e8:
            s = f"${v/1e8:,.{digits}f}亿"
        else:
            s = f"${v/1e4:,.0f}万"
    else:
        s = f"${v/1e9:,.{digits}f}B" if v >= 1e9 else f"${v/1e6:,.0f}M"
    return ("−" if neg else "") + s


def unit(v, lang):
    """Bare number in the chart unit (亿 for zh, B for en)."""
    if v is None:
        return ""
    return f"{v/1e8:,.0f}" if lang == "zh" else f"{v/1e9:,.1f}"


def pct(v, sign=True):
    if v is None:
        return "—"
    return f"{v*100:+.1f}%".replace("-", "−") if sign else f"{v*100:.1f}%".replace("-", "−")


def qlabel(end):
    return f"{end[2:4]}.{int(end[5:7]):02d}"


def yoy_of(trend, key, d):
    """YoY using the trend list (4 quarters back, or 1 fiscal year back)."""
    lag = 1 if is_annual(d) else 4
    if len(trend) < lag + 1:
        return None
    cur, prev = trend[-1].get(key), trend[-1 - lag].get(key)
    if cur is None or not prev:
        return None
    return (cur - prev) / abs(prev)


# ---------- shared chrome ----------
CURRENT_PAGE = ""
class Card:
    def __init__(self, w, h, t):
        self.w, self.h, self.t = w, h, t
        apply_style(t)
        self.o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
                  f'<rect width="{w}" height="{h}" fill="{t["bg"]}"/>']
        if t.get("bg_grad"):   # gradient page: a solid bg rect underneath, for renderers without gradient support
            _AV[0] += 1
            gid = f"bg{_AV[0]}"
            stops = t["bg_grad"]
            st = "".join(f'<stop offset="{i / max(len(stops) - 1, 1):.2f}" stop-color="{col}"/>' for i, col in enumerate(stops))
            self.o.append(f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">{st}</linearGradient></defs>'
                          f'<rect width="{w}" height="{h}" fill="url(#{gid})"/>')

    def add(self, *parts):
        self.o.extend(parts)

    def rect(self, x, y, w, h, fill, rx=0, extra=""):
        rx = min(rx * self.t.get("round", 1), max(h, 0) / 2, max(w, 0) / 2) if rx else 0
        self.o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" height="{max(h,0):.1f}" rx="{rx:g}" fill="{fill}" {extra}/>')

    def box(self, x, y, w, h, rx=18):
        t = self.t
        sw = t.get("stroke", 1.5)
        extra = f'stroke="{t.get("card_stroke", t["faint"])}" stroke-width="{sw}"' if sw else ""
        if sw and t.get("card_stroke_opacity") is not None:
            extra += f' stroke-opacity="{t["card_stroke_opacity"]}"'
        if t.get("card_opacity") is not None:
            extra += f' fill-opacity="{t["card_opacity"]}"'
        self.rect(x, y, w, h, t["card"], rx, extra)

    def svg(self):
        return "\n".join(self.o + ["</svg>"])


def company_name(d):
    n = d["company"]
    return n.title() if n.isupper() else n


_AV = [0]


def footer(c, d, l, lang, P, page=None):
    t = c.t
    fy = c.h - 56
    c.rect(P, fy - 38, c.w - 2 * P, 1.5, t["faint"])
    filing = f'{d["form"].replace(" (derived)", "")} · {d["filed"]} {l["filed"]}'
    handle = t.get("handle")
    right = (f"{handle} · " if handle else "") + "earnings-card" + (f"  {CURRENT_PAGE}" if page and CURRENT_PAGE else "")
    left = f'{l["note"]} · {filing}'
    room = c.w - 2 * P - measure(right, 18, 700) - (36 if t.get("avatar") else 0) - 28
    c.add(text(P, fy, left, fit(left, room, 18, 400, floor=12), t["sub"]))   # long handles shrink the left note
    c.add(text(c.w - P, fy, right, 18, t["ink"], 700, "end"))
    if t.get("avatar"):
        ax = c.w - P - measure(right, 18, 700) - 22
        _AV[0] += 1   # unique per card, so many cards inlined in one web page don't share a clip path
        cid = f"av{_AV[0]}"
        c.add(f'<clipPath id="{cid}"><circle cx="{ax:.1f}" cy="{fy-6}" r="14"/></clipPath>'
              f'<image href="{t["avatar"]}" x="{ax-14:.1f}" y="{fy-20}" width="28" height="28" '
              f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{cid})"/>')


def small_header(c, d, l, title, subtitle, P):
    t = c.t
    right = f'{d.get("fiscal_label","")} · {l["ended"]} {d["period_end"]}'
    if c.h <= 1080:   # 1:1 and 16:9: a tighter header leaves room for the chart
        tw = measure(d["ticker"], 30, 800, -0.5)
        room = c.w - 2 * P - tw - 14 - measure(right, 18, 500) - 24
        c.add(text(P, 100, d["ticker"], 30, t["ink"], 800, ls=-0.5))
        c.add(text(P + tw + 14, 100, clip(company_name(d), room, 20, 500), 20, t["sub"], 500))
        c.add(text(c.w - P, 100, right, 18, t["sub"], 500, "end"))
        c.rect(P, 122, c.w - 2 * P, 2, t["ink"])
        with display_font():
            c.add(text(P, 190, title, fit(title, c.w - 2 * P, 48, 800, -1), t["ink"], 800, ls=-1))
        if subtitle:
            sz = fit(subtitle, c.w - 2 * P, 24, 500, floor=20)
            c.add(text(P, 236, clip(subtitle, c.w - 2 * P, sz, 500), sz, t["sub"], 500))
        return 284
    tw = measure(d["ticker"], 34, 800, -0.5)
    room = c.w - 2 * P - tw - 16 - measure(right, 20, 500) - 24
    c.add(text(P, 112, d["ticker"], 34, t["ink"], 800, ls=-0.5))
    c.add(text(P + tw + 16, 112, clip(company_name(d), room, 22, 500), 22, t["sub"], 500))
    c.add(text(c.w - P, 112, right, 20, t["sub"], 500, "end"))
    c.rect(P, 140, c.w - 2 * P, 2, t["ink"])
    with display_font():
        c.add(text(P, 224, title, fit(title, c.w - 2 * P, 54, 800, -1), t["ink"], 800, ls=-1))
    if subtitle:
        sz = fit(subtitle, c.w - 2 * P, 26, 500, floor=21)
        c.add(text(P, 278, clip(subtitle, c.w - 2 * P, sz, 500), sz, t["sub"], 500))
    return 330


def metric_cells(d, l, lang):
    gm_delta = None
    if d.get("gross_margin") is not None and d.get("gross_margin_prev") is not None:
        gm_delta = (d["gross_margin"] - d["gross_margin_prev"]) * 100
    return [
        (l["gm"], pct(d["gross_margin"], False),
         None if gm_delta is None else (f'{gm_delta:+.1f} {l["pts"]}'.replace("-", "−"), gm_delta >= 0)),
        (l["om"], pct(d["operating_margin"], False), ("·" + money(d.get("operating_income"), lang), None)),
        (l["ni"], money(d["net_income"], lang),
         None if d["net_income_yoy"] is None else (f'{pct(d["net_income_yoy"])} {l["yoy"]}', d["net_income_yoy"] >= 0)),
        (l["eps"], "—" if d["eps"] is None else f'${d["eps"]:.2f}',
         None if d["eps_yoy"] is None else (f'{pct(d["eps_yoy"])} {l["yoy"]}', d["eps_yoy"] >= 0)),
    ]


def draw_cell(c, x, y, w, h, lab, val, delta, vsize=54):
    t = c.t
    c.box(x, y, w, h, 18)
    c.add(text(x + 28, y + 48, lab, 22, t["sub"], 500))
    c.add(text(x + 28, y + 48 + vsize * 1.18, val, vsize, t["ink"], 800, ls=-1))
    if delta:
        s, good = delta
        col = t["sub"] if good is None else (t["up"] if good else t["down"])
        c.add(text(x + 28, y + h - 22, s.lstrip("·"), 21, col, 700 if good is not None else 500))


def draw_cell_c(c, x, y, w, h, lab, val, delta, vsize=40, lsize=20, dsize=18):
    """A metric box for the tighter layouts: every line shrinks to fit the box."""
    t = c.t
    c.box(x, y, w, h, 16)
    inner = w - 44
    c.add(text(x + 22, y + lsize + 18, lab, fit(lab, inner, lsize, 500), t["sub"], 500))
    vs = fit(val, inner, vsize, 800, -1)
    c.add(text(x + 22, round(y + lsize + 22 + vsize * 1.12), val, vs, t["ink"], 800, ls=-1))
    if delta:
        s, good = delta
        s = s.lstrip("·")
        col = t["sub"] if good is None else (t["up"] if good else t["down"])
        wgt = 700 if good is not None else 500
        c.add(text(x + 22, y + h - 18, s, fit(s, inner, dsize, wgt), col, wgt))


def pill(c, x_right, y, label, size, color, h=None):
    """Rounded YoY badge whose right edge is x_right; y is its top."""
    t = c.t
    h = h or round(size * 2.1)
    pw = measure(label, size, 700) + 2 * size
    c.rect(x_right - pw, y, pw, h, color, h / 2)
    c.add(text(x_right - pw / 2, round(y + h / 2 + size * 0.36), label, size, t["bg"], 700, "middle"))
    return pw


def bars(c, x, y, w, h, vals, labels, lang, highlight_last=True, label_fn=None):
    """Vertical bars with value labels; supports negatives."""
    t = c.t
    label_fn = label_fn or (lambda v: unit(v, lang))
    vs = [v or 0 for v in vals]
    hi, lo = max(max(vs), 0), min(min(vs), 0)
    span = (hi - lo) or 1
    top_pad = 34
    usable = h - top_pad
    zero = y + top_pad + usable * hi / span
    n = len(vs)
    gap = 18 if w > 700 else 12
    bw = (w - gap * (n - 1)) / n
    if lo < 0:
        c.rect(x, zero - 0.75, w, 1.5, t["faint"])
    for i, v in enumerate(vs):
        bx = x + i * (bw + gap)
        bh = max(3, abs(v) / span * usable)
        last = highlight_last and i == n - 1
        col = t.get("hi", t["ink"]) if last else t["bar"]
        if v < 0:
            col = t["down"]
        by = zero - bh if v >= 0 else zero
        c.rect(bx, by, bw, bh, col, 6)
        ly = by - 10 if v >= 0 else zero - 10
        c.add(text(bx + bw / 2, ly, label_fn(vals[i]), 17, t["ink"] if last else t["sub"], 700 if last else 500, "middle"))
        c.add(text(bx + bw / 2, y + h + 30, labels[i], 18, t["sub"], 500, "middle"))


# ---------- cards ----------
def card_cover(d, l, lang, t, headline, size=None):
    W, H = size or (1080, 1350)
    if W > H:      # landscape: the wide layout, scaled to the requested size
        return _scaled(card_wide(d, l, lang, t, headline), W, H)
    if W == H:
        return _cover_square(d, l, lang, t, headline, W, H)
    P = 80
    e = H - 1350   # extra height of taller portrait ratios (9:16), shared out below
    c = Card(W, H, t)
    c.add(text(P, 150, d["ticker"], 92, t["ink"], 800, ls=-2))
    c.add(text(P, 196, company_name(d), 24, t["sub"], 500))
    c.add(text(W - P, 118, d.get("fiscal_label", ""), 30, t["ink"], 700, "end"))
    c.add(text(W - P, 156, f'{l["ended"]} {d["period_end"]}', 22, t["sub"], 400, "end"))
    y = 236
    c.rect(P, y, W - 2 * P, 2, t["ink"])
    y += 70 + e * 5 // 100
    if headline:
        with display_font():
            lines = wrap(headline, W - 2 * P, 44, 700)
            for i, line in enumerate(lines):
                c.add(text(P, y + i * 58, line, 44, t["ink"], 700))
        y += 58 * len(lines) + 20
    else:
        y -= 10
        lines = []
    c.add(text(P, y + 10, l["rev"], 26, t["sub"], 500))
    up = (d["revenue_yoy"] or 0) >= 0
    c.add(text(P - 4, y + 120, money(d["revenue"], lang), 112, t["ink"], 800, ls=-3))
    pill = f'{pct(d["revenue_yoy"])} {l["yoy"]}'
    pw = measure(pill, 26, 700) + 56
    c.rect(W - P - pw, y + 62, pw, 56, t["up"] if up else t["down"], 28)
    c.add(text(W - P - pw / 2, y + 99, pill, 26, t["bg"], 700, "middle"))
    y += 180
    c.add(text(P, y, l["trend"].format(n=len(d["trend"])), 22, t["sub"], 500))
    y += 24
    bh = (230 if headline else 290) + e * 60 // 100 - 58 * max(len(lines) - 1, 0)   # a 2-line headline takes it from the bars
    bars(c, P, y, W - 2 * P, bh, [q["revenue"] for q in d["trend"]],
         [plabel(q) for q in d["trend"]], lang)
    y += bh + 74 + e * 6 // 100
    cw, chh, g = (W - 2 * P - 24) / 2, 168 + e * 12 // 100, 24
    for i, (lab, val, delta) in enumerate(metric_cells(d, l, lang)):
        draw_cell(c, P + (i % 2) * (cw + g), y + (i // 2) * (chh + g), cw, chh, lab, val, delta,
                  vsize=54 if chh < 200 else 62)
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def _cover_square(d, l, lang, t, headline, W, H):
    P = 80
    c = Card(W, H, t)
    c.add(text(P, 128, d["ticker"], 80, t["ink"], 800, ls=-2))
    c.add(text(P, 170, company_name(d), 22, t["sub"], 500))
    c.add(text(W - P, 104, d.get("fiscal_label", ""), 28, t["ink"], 700, "end"))
    c.add(text(W - P, 140, f'{l["ended"]} {d["period_end"]}', 20, t["sub"], 400, "end"))
    c.rect(P, 196, W - 2 * P, 2, t["ink"])
    y = 258
    if headline:
        with display_font():
            lines = wrap(headline, W - 2 * P, 40, 700)
            for i, line in enumerate(lines):
                c.add(text(P, y + i * 52, line, 40, t["ink"], 700))
        y += 52 * len(lines) + 14
    else:
        y -= 10
    c.add(text(P, y + 10, l["rev"], 22, t["sub"], 500))
    up = (d["revenue_yoy"] or 0) >= 0
    pw = pill(c, W - P, y + 50, f'{pct(d["revenue_yoy"])} {l["yoy"]}', 24, t["up"] if up else t["down"], 50)
    rv = money(d["revenue"], lang)
    c.add(text(P - 4, y + 106, rv, fit(rv, W - 2 * P - pw - 30, 96, 800, -3), t["ink"], 800, ls=-3))
    y += 148
    c.add(text(P, y, l["trend"].format(n=len(d["trend"])), 20, t["sub"], 500))
    y += 22
    chh = 132
    cy = H - 130 - chh
    bars(c, P, y, W - 2 * P, cy - 56 - y, [q["revenue"] for q in d["trend"]], [plabel(q) for q in d["trend"]], lang)
    g = 16
    cw = (W - 2 * P - 3 * g) / 4
    for i, (lab, val, delta) in enumerate(metric_cells(d, l, lang)):
        draw_cell_c(c, P + i * (cw + g), cy, cw, chh, lab, val, delta)
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def _scaled(svg, W, H):
    """Show an SVG at another pixel size with the same aspect (viewBox does the scaling)."""
    head, rest = svg.split("\n", 1)
    head = re.sub(r'width="\d+" height="\d+"', f'width="{W}" height="{H}"', head, count=1)
    return head + "\n" + rest


def card_profit(d, l, lang, t, size=None):
    W, H = size or (1080, 1350)
    P = 80
    c = Card(W, H, t)
    rev, ni = d["revenue"], d["net_income"]
    keep = round(ni / rev * 100) if ni is not None and rev else None
    sub = (f"每 100 美元营收，最后留下 {keep} 美元净利润" if lang == "zh"
           else f"Of every $100 in revenue, ${keep} ends up as net income") if keep is not None else ""
    y = small_header(c, d, l, l["profit_t"], sub, P)

    cost = d.get("cost_of_revenue")
    gp = rev - cost if cost is not None else None
    oi = d.get("operating_income")
    rows = [(l["rev"], rev, "total")]
    if cost is not None:
        rows += [(l["cost"], -cost, "step"), (l["gp"], gp, "total")]
    opex_named = 0
    if gp is not None and oi is not None:
        for lab, key in ((l["rnd"], "rnd"), (l["sga"], "sga")):
            if d.get(key):
                rows.append((lab, -d[key], "step"))
                opex_named += d[key]
        other_opex = gp - oi - opex_named
        if abs(other_opex) > rev * 0.005:
            rows.append((l["other_opex"], -other_opex, "step"))
    if oi is not None:
        rows.append((l["oi"], oi, "total"))
    if oi is not None and ni is not None:
        tax = d.get("tax")
        if tax:
            rows.append((l["tax"], -tax, "step"))
        other = ni - oi + (tax or 0)
        if abs(other) > rev * 0.005:
            rows.append((l["other"], other, "step"))
        rows.append((l["ni"], ni, "total"))
    elif ni is not None and cost is None:   # banks / insurers: no cost of revenue or operating income line
        rows += [(l["all_costs"], ni - rev, "step"), (l["ni"], ni, "total")]

    avail = H - 140 - y
    rh = min(92 if H <= 1350 else 92 * H // 1350, avail / max(len(rows), 1))
    tight = rh < 66   # 1:1 and 16:9: one line per row, share of revenue beside the amount
    fs = (22, 20, 24, 21) if tight else (26, 23, 28, 24)   # label total/step, value total/step
    label_w = max(measure(r[0], fs[0], 700) for r in rows) + 36
    val_w = 270 if tight else 210
    bx0, bw_max = P + label_w, W - 2 * P - label_w - val_w
    scale = bw_max / max(rev, 1)
    level = 0
    for i, (lab, v, kind) in enumerate(rows):
        ry = y + i * rh
        total = kind == "total"
        if total:
            x0, x1 = bx0, bx0 + max(v, 0) * scale
            col = t["ink"] if lab in (l["rev"], l["ni"]) else t["a2"]
            level = v
        else:
            new = level + v
            x0, x1 = bx0 + min(level, new) * scale, bx0 + max(level, new) * scale
            col = t["bar"] if v < 0 else t["up"]
            level = new
        vs = money(v, lang) if total else ("−" if v < 0 else "+") + money(abs(v), lang)
        share = f'{abs(v)/rev*100:.1f}% {l["of_rev"]}'
        if tight:
            ty = round(ry + rh * 0.5 + 8, 1)
            c.add(text(P, ty, lab, fs[0] if total else fs[1], t["ink"] if total else t["sub"], 700 if total else 500))
            c.rect(x0, ry + rh * 0.2, max(x1 - x0, 3), rh * 0.6, col, 6)
            vsz, vw = (fs[2], 800) if total else (fs[3], 600)
            c.add(text(W - P, ty, vs, vsz, t["ink"], vw, "end"))
            c.add(text(W - P - measure(vs, vsz, vw) - 12, ty, f'{abs(v)/rev*100:.1f}%', 16, t["sub"], 500, "end"))
        else:
            c.add(text(P, ry + rh * 0.5 + 9, lab, 26 if total else 23, t["ink"] if total else t["sub"], 700 if total else 500))
            c.rect(x0, ry + rh * 0.18, max(x1 - x0, 3), rh * 0.64, col, 8)
            c.add(text(W - P, ry + rh * 0.5 + 2, vs, 28 if total else 24, t["ink"], 800 if total else 600, "end"))
            c.add(text(W - P, ry + rh * 0.5 + 28, share, 17, t["sub"], 500, "end"))
        if total and i < len(rows) - 1:
            c.rect(x1 - 1, ry + rh * 0.82, 1.5, rh * 0.36, t["faint"])
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def line_chart(c, x, y, w, h, series, labels, lang):
    """series: list of (name, values[0..1], color). Values are ratios."""
    t = c.t
    allv = [v for _, vs, _ in series for v in vs if v is not None]
    if not allv:
        return
    hi, lo = max(allv), min(allv)
    hi, lo = hi + 0.06, max(-1, lo - 0.06) if lo < 0 else max(0, lo - 0.06)
    n = len(labels)
    right_pad = 150
    px = lambda i: x + i * (w - right_pad) / max(n - 1, 1)
    py = lambda v: y + h - (v - lo) / (hi - lo) * h
    for k in range(5):
        gv = lo + (hi - lo) * k / 4
        c.rect(x, py(gv), w - right_pad, 1, t["faint"])
        c.add(text(x - 12, py(gv) + 6, f"{gv*100:.0f}%", 15, t["sub"], 500, "end"))
    ends = []
    for name, vs, col in series:
        pts = [(px(i), py(v)) for i, v in enumerate(vs) if v is not None]
        if len(pts) < 2:
            continue
        c.add(f'<polyline points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="none" stroke="{col}" '
              f'stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
        for a, b in pts[:-1]:
            c.add(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4" fill="{t["bg"]}" stroke="{col}" stroke-width="2.5"/>')
        a, b = pts[-1]
        c.add(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="8" fill="{col}"/>')
        ends.append([b + 7, a, name, [v for v in vs if v is not None][-1], col])
    # spread end labels so they never overlap
    ends.sort(key=lambda e: e[0])
    gap = 54
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
    overflow = ends[-1][0] - (y + h - 24) if ends else 0
    if overflow > 0:
        for e in ends:
            e[0] -= overflow
        for i in range(len(ends) - 2, -1, -1):
            ends[i][0] = min(ends[i][0], ends[i + 1][0] - gap)
    for ly, a, name, v, col in ends:
        c.add(text(a + 20, ly - 4, f"{v*100:.1f}%", 26, col, 800))
        c.add(text(a + 20, ly + 20, name, 16, t["sub"], 500))
    for i, lab in enumerate(labels):
        c.add(text(px(i), y + h + 32, lab, 17, t["sub"], 500, "middle"))


def card_trend(d, l, lang, t, size=None):
    W, H = size or (1080, 1350)
    P = 80
    c = Card(W, H, t)
    tr = d["trend"]
    g0, g1 = tr[0].get("gross_margin"), tr[-1].get("gross_margin")
    n0, n1 = tr[0].get("net_margin"), tr[-1].get("net_margin")
    if n0 is not None and n1 is not None:
        sub = (f"净利率 {len(tr)} {l['n_per']}从 {n0*100:.1f}% 到 {n1*100:.1f}%" if lang == "zh"
               else f"Net margin went from {n0*100:.1f}% to {n1*100:.1f}% in {len(tr)} {l['n_per']}")
    else:
        sub = ""
    y = small_header(c, d, l, l["trend_t"].format(n=len(tr)), sub, P)
    c.add(text(P, y + 10, l["margins"], 22, t["sub"], 500))
    series = [(l["gm"], [q.get("gross_margin") for q in tr], t["a1"]),
              (l["om"], [q.get("operating_margin") for q in tr], t["a2"]),
              (l["nm"], [q.get("net_margin") for q in tr], t["a3"])]
    labels = [plabel(q) for q in tr]
    bottom = H - 150   # lowest bar baseline; axis labels sit 30px below it
    if W > H:          # 16:9: margins on the left, net income on the right
        lw = (W - 2 * P) * 6 // 10
        line_chart(c, P + 50, y + 50, lw - 50, bottom - y - 50, series, labels, lang)
        rx = P + lw + 80
        c.add(text(rx, y + 10, l["ni_bars"], 22, t["sub"], 500))
        bars(c, rx, y + 34, W - P - rx, bottom - y - 34, [q.get("net_income") for q in tr], labels, lang)
    elif W == H:
        ch = 270
        line_chart(c, P + 50, y + 44, W - 2 * P - 50, ch, series, labels, lang)
        y += 44 + ch + 84
        c.add(text(P, y, l["ni_bars"], 22, t["sub"], 500))
        bars(c, P, y + 24, W - 2 * P, bottom - y - 24, [q.get("net_income") for q in tr], labels, lang)
    else:
        e = H - 1350
        ch = 420 + e * 6 // 10
        line_chart(c, P + 50, y + 50, W - 2 * P - 50, ch, series, labels, lang)
        y += 140 + ch
        c.add(text(P, y, l["ni_bars"], 22, t["sub"], 500))
        bars(c, P, y + 24, W - 2 * P, 250 + e * 4 // 10, [q.get("net_income") for q in tr], labels, lang)
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def card_cash(d, l, lang, t, size=None):
    W, H = size or (1080, 1350)
    P = 80
    c = Card(W, H, t)
    fcf = d.get("fcf")
    ret = (d.get("buyback") or 0) + (d.get("dividends") or 0)
    if fcf and ret:
        sub = (f"{l['cur']}回购加分红 {money(ret, lang)}，相当于自由现金流的 {ret/fcf*100:.0f}%" if lang == "zh" and fcf > 0
               else f"{l['cur']}回购加分红 {money(ret, lang)}" if lang == "zh"
               else f"{money(ret, lang)} returned to shareholders, {ret/fcf*100:.0f}% of free cash flow" if fcf > 0
               else f"{money(ret, lang)} returned to shareholders")
    else:
        sub = l["fcf_note"]
    y = small_header(c, d, l, l["cash_t"], sub, P)
    lag = 1 if is_annual(d) else 4
    fy = yoy_of(d["trend"], "fcf", d)
    show_pill = fy is not None and (d["trend"][-1 - lag].get("fcf") or 0) > 0 and (fcf or 0) > 0
    cells = [(l["ocf"], money(d.get("ocf"), lang), None),
             (l["capex"], money(d.get("capex"), lang),
              (f'{d["capex"]/d["revenue"]*100:.1f}% {l["of_rev"]}', None) if d.get("capex") else None),
             ((l["returned"], money(ret, lang),
               (f'{l["buyback"]} {money(d.get("buyback"), lang)} · {l["div"]} {money(d.get("dividends"), lang)}', None))
              if ret else (l["capex_ocf"], f'{d["capex"]/d["ocf"]*100:.0f}%' if d.get("capex") and d.get("ocf") else "—", None)),
             (l["cashpile"] if d.get("securities") else l["cashonly"], money((d.get("cash") or 0) + (d.get("securities") or 0), lang) if d.get("cash") else "—", None)]
    bar_vals, bar_labels = [q.get("fcf") for q in d["trend"]], [plabel(q) for q in d["trend"]]
    fcol = t["ink"] if (fcf or 0) >= 0 else t["down"]

    if W > H or W == H:   # 16:9 (figures left, bars right) and 1:1 (all stacked, tighter)
        land = W > H
        colw = 820 if land else W - 2 * P
        c.add(text(P, y + 10, l["fcf"], 22, t["sub"], 500))
        pw = pill(c, P + colw, y + 48, f'{pct(fy)} {l["yoy"]}', 24, t["up"] if fy >= 0 else t["down"], 50) if show_pill else 0
        fv = money(fcf, lang)
        c.add(text(P - 4, y + 100, fv, fit(fv, colw - pw - 30, 88, 800, -3), fcol, 800, ls=-3))
        y += 140
        g = 18
        chh = min(190, (H - 120 - y - g) // 2) if land else 132
        cw = (colw - g) / 2
        for i, (lab, val, delta) in enumerate(cells):
            draw_cell_c(c, P + (i % 2) * (cw + g), y + (i // 2) * (chh + g), cw, chh, lab, val, delta,
                        vsize=46 if land else 40)
        if land:
            rx = P + colw + 80
            c.add(text(rx, 294, l["fcf_bars"], 22, t["sub"], 500))
            bars(c, rx, 318, W - P - rx, H - 150 - 318, bar_vals, bar_labels, lang)
        else:
            y += 2 * chh + g + 54
            c.add(text(P, y, l["fcf_bars"], 22, t["sub"], 500))
            bars(c, P, y + 24, W - 2 * P, H - 150 - y - 24, bar_vals, bar_labels, lang)
        footer(c, d, l, lang, P, "__PAGE__")
        return c.svg()

    e = H - 1350
    # Big FCF
    c.add(text(P, y + 10, l["fcf"], 26, t["sub"], 500))
    c.add(text(P - 4, y + 112, money(fcf, lang), 100, fcol, 800, ls=-3))
    if show_pill:
        pill_s = f'{pct(fy)} {l["yoy"]}'
        pw = measure(pill_s, 26, 700) + 56
        c.rect(W - P - pw, y + 56, pw, 56, t["up"] if fy >= 0 else t["down"], 28)
        c.add(text(W - P - pw / 2, y + 93, pill_s, 26, t["bg"], 700, "middle"))
    y += 160 + e * 10 // 100

    # Cells
    cw, chh, g = (W - 2 * P - 24) / 2, 164 + e * 10 // 100, 24
    for i, (lab, val, delta) in enumerate(cells):
        draw_cell(c, P + (i % 2) * (cw + g), y + (i // 2) * (chh + g), cw, chh, lab, val, delta,
                  vsize=46 if chh < 200 else 56)
    y += 2 * chh + g + 60
    c.add(text(P, y, l["fcf_bars"], 22, t["sub"], 500))
    bars(c, P, y + 24, W - 2 * P, H - y - 210, bar_vals, bar_labels, lang)
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def card_wide(d, l, lang, t, headline):
    W, H, P = 1600, 900, 72
    c = Card(W, H, t)
    c.add(text(P, 128, d["ticker"], 84, t["ink"], 800, ls=-2))
    c.add(text(P + measure(d["ticker"], 84, 800, -2) + 24, 128, company_name(d), 26, t["sub"], 500))
    c.add(text(W - P, 100, d.get("fiscal_label", ""), 30, t["ink"], 700, "end"))
    c.add(text(W - P, 136, f'{l["ended"]} {d["period_end"]}', 22, t["sub"], 400, "end"))
    c.rect(P, 172, W - 2 * P, 2, t["ink"])
    left_w = 700
    y = 252
    if headline:
        with display_font():
            lines = wrap(headline, left_w, 44, 700)
            for i, line in enumerate(lines):
                c.add(text(P, y + i * 58, line, 44, t["ink"], 700))
        y += 58 * len(lines) + 24
    c.add(text(P, y, l["rev"], 22, t["sub"], 500))
    rv = money(d["revenue"], lang)
    c.add(text(P - 4, y + 96, rv, 96, t["ink"], 800, ls=-3))
    up = (d["revenue_yoy"] or 0) >= 0
    pill = f'{pct(d["revenue_yoy"])} {l["yoy"]}'
    pw = measure(pill, 24, 700) + 48
    px0 = P + measure(rv, 96, 800, -3) + 28
    c.rect(px0, y + 44, pw, 52, t["up"] if up else t["down"], 26)
    c.add(text(px0 + pw / 2, y + 79, pill, 24, t["bg"], 700, "middle"))
    my = max(y + 136, 520)
    cw, chh, g = (left_w - 20) / 2, 118, 18
    for i, (lab, val, delta) in enumerate(metric_cells(d, l, lang)):
        x = P + (i % 2) * (cw + g)
        yy = my + (i // 2) * (chh + g)
        c.box(x, yy, cw, chh, 16)
        c.add(text(x + 22, yy + 36, lab, 18, t["sub"], 500))
        c.add(text(x + 22, yy + 92, val, 42, t["ink"], 800, ls=-1))
        if delta:
            s_, good = delta
            col = t["sub"] if good is None else (t["up"] if good else t["down"])
            c.add(text(x + cw - 20, yy + 36, s_.lstrip("·"), 17, col, 700 if good is not None else 500, "end"))
    rx = P + left_w + 70
    rw = W - P - rx
    c.add(text(rx, 252, l["trend"].format(n=len(d["trend"])), 20, t["sub"], 500))
    bars(c, rx, 272, rw, my + 2 * chh + g - 272 - 46, [q["revenue"] for q in d["trend"]],
         [plabel(q) for q in d["trend"]], lang)
    footer(c, d, l, lang, P)
    return c.svg()


PALETTE = {"light": ["#151515", "#8C6A3F", "#B9A27E", "#6F6A60", "#CFC8BA", "#E3DDD1", "#A8A296", "#EFEAE0"],
           "dark": ["#F2EFE8", "#D9A65E", "#9C7C4E", "#9A958B", "#5A5650", "#3A3733", "#77736B", "#2E2C29"]}


def card_mix(d, l, lang, t, labels=None, size=None):
    W, H = size or (1080, 1350)
    P = 80
    c = Card(W, H, t)
    seg = d.get("segments") or {}
    labels = labels or {}
    groups = []
    first = "product" if "product" in seg else ("segment" if "segment" in seg else None)
    if first:
        groups.append((l["by_product"] if first == "product" else l["by_segment"], seg[first]))
    second = "geo" if "geo" in seg else ("segment" if first == "product" and "segment" in seg else None)
    if second:
        groups.append((l["by_geo"] if second == "geo" else l["by_segment"], seg[second]))
    top = groups[0][1][0] if groups else None
    if top:
        name = labels.get(top["label"], top["label"])
        sep = " " if name[-1:].isascii() else ""
        sub = (f"{name}{sep}贡献了 {top['share']*100:.0f}% 的营收" if lang == "zh"
               else f"{name}: {top['share']*100:.0f}% of revenue")
    else:
        sub = ""
    y = small_header(c, d, l, l["mix_t"], sub, P)
    pal = t.get("palette") or PALETTE["light"]
    side = W > H and len(groups) == 2   # 16:9: the two breakdowns side by side
    avail = H - 130 - y
    if W == H:
        max_rows = [min(len(g[1]), 6 if len(groups) == 1 else 4) for g in groups]
    else:
        max_rows = [min(len(g[1]), 6 if len(groups) == 1 else 5) for g in groups]
    per_group_fixed = 120
    cap = 76 if H <= 1350 else 76 * H // 1350
    if side:
        rh = min(cap, (avail - per_group_fixed) / max(max(max_rows), 1))
    else:
        rh = min(cap, (avail - per_group_fixed * len(groups)) / max(sum(max_rows), 1))
    y0 = y
    for gi, (title, items) in enumerate(groups):
        cw = (W - 2 * P - 80) // 2 if side else W - 2 * P
        x0 = P + gi * (cw + 80) if side else P
        if side:
            y = y0
        items = list(items)
        if len(items) > max_rows[gi]:
            keep = items[:max_rows[gi] - 1]
            rest = items[max_rows[gi] - 1:]
            items = keep + [{"label": l["other_seg"], "value": sum(i["value"] for i in rest),
                             "share": sum(i.get("share") or 0 for i in rest), "yoy": None}]
        c.add(text(x0, y + 6, title, 24, t["ink"], 700))
        # 100% stacked bar
        x = x0
        bw = cw
        by = y + 26
        for k, it in enumerate(items):
            w = bw * (it.get("share") or 0)
            c.rect(x, by, max(w - 3, 1), 30, pal[k % len(pal)], 4)
            x += w
        y = by + 30 + 34
        for k, it in enumerate(items):
            ry = y + k * rh
            c.rect(x0, ry - 14, 14, 14, pal[k % len(pal)], 3)
            name = labels.get(it["label"], it["label"])
            mv = money(it["value"], lang)
            name_w = min(cw - 450, cw - 280 - measure(mv, 26, 800) - 40)   # never run into the amount
            if measure(name, 24, 500) > name_w:
                while measure(name + "…", 24, 500) > name_w and len(name) > 4:
                    name = name[:-1]
                name += "…"
            c.add(text(x0 + 28, ry, name, 24, t["ink"], 500))
            c.add(text(x0 + cw - 280, ry, mv, 26, t["ink"], 800, "end"))
            c.add(text(x0 + cw - 160, ry, f'{(it.get("share") or 0)*100:.0f}%', 22, t["sub"], 500, "end"))
            yy = it.get("yoy")
            if yy is not None:
                ys_ = f'{pct(yy)} {l["yoy"]}'
                c.add(text(x0 + cw, ry, ys_, fit(ys_, 146, 22, 700, floor=13), t["up"] if yy >= 0 else t["down"], 700, "end"))
            c.rect(x0, ry + rh * 0.42, cw, 1, t["faint"])
        y += len(items) * rh + 40
        if gi == 0 and len(groups) == 2 and not side and H > 1350:   # 9:16: spread the spare height between groups
            used = sum(per_group_fixed + rh * min(len(g_[1]), max_rows[k]) for k, g_ in enumerate(groups))
            y += max(0, avail - used) // 3
    if not groups:
        c.add(text(P, y + 40, "No segment breakdown in this filing." if lang == "en" else "本期财报没有披露分业务数据", 28, t["sub"], 500))
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def _gfmt(v, it, lang, digits=1):
    if it.get("unit") == "pct":
        return f"{v*100:.1f}%"
    return money(v, lang, 0 if (lang == "zh" and abs(v) >= 1e10 and digits == 0) else 1)


def _grange(it, lang):
    lo, hi = it["low"], it["high"]
    if abs(hi - lo) < 1e-9:
        return ("约 " if lang == "zh" else "~") + _gfmt(lo, it, lang)
    if it.get("unit") == "pct":
        return f"{lo*100:.1f}%–{hi*100:.1f}%"
    if it.get("display"):
        return it["display"]
    return f"{_gfmt(lo, it, lang, 0)}–{_gfmt(hi, it, lang, 0)}"


def _gdelta(it, base, lang, l):
    mid = (it["low"] + it["high"]) / 2
    if it.get("unit") == "pct":
        dv = (mid - base) * 100
        return f'{dv:+.1f} {l["pts"]}'.replace("-", "−"), dv
    if not base:
        return None, 0
    dv = (mid - base) / abs(base)
    return pct(dv), dv


def card_guide(d, l, lang, t, g, size=None):
    W, H = size or (1080, 1350)
    P = 80
    c = Card(W, H, t)
    nxt = (g.get("next") or {}).get("items") or []
    first = nxt[0] if nxt else None
    sub = ""
    if first and first.get("base"):
        ds, dv = _gdelta(first, first["base"], lang, l)
        mid = (first["low"] + first["high"]) / 2
        if lang == "zh":
            sub = f'下季{first["metric"]}指引中值 {_gfmt(mid, first, lang)}，{"比本季" if dv >= 0 else "比本季"} {ds}'
        else:
            sub = f'Next-quarter {first["metric"].lower()} guided to {_gfmt(mid, first, lang)}, {ds} vs this quarter'
    y = small_header(c, d, l, l["guide_t"], sub, P)
    land, square, e = W > H, W == H, max(H - 1350, 0)
    x0, cw = P, (820 if land else W - 2 * P)
    # box height, gap, label / value sizes, prior-row height
    rh, gap, lsz, vsz, prh = (84, 12, 20, 32, 100) if square else (108 + e * 4 // 100, 16 + e // 100, 22, 38, 118 + e * 4 // 100)
    foot_y = H - 160

    # next quarter outlook
    c.add(text(x0, y + 6, f'{l["next_g"]} · {g["next"].get("period", "")}', 24, t["ink"], 700))
    top = y
    y += 40
    for k, it in enumerate(nxt[:4]):
        ry = y + k * (rh + gap)
        c.box(x0, ry, cw, rh, 16)
        c.add(text(x0 + 28, ry + rh // 2 - 12, it["metric"], lsz, t["sub"], 500))
        c.add(text(x0 + 28, ry + rh // 2 + 34, _grange(it, lang), vsz, t["ink"], 800, ls=-0.5))
        if it.get("base") is not None:
            ds, dv = _gdelta(it, it["base"], lang, l)
            if ds:
                col = t["sub"] if it.get("lower_is_better") else (t["up"] if dv >= 0 else t["down"])
                c.add(text(x0 + cw - 28, ry + rh // 2 - 2, ds, 30 if not square else 26, col, 800, "end"))
                c.add(text(x0 + cw - 28, ry + rh // 2 + 32, f'{l["vs_now"]} {_gfmt(it["base"], it, lang)}', 20, t["sub"], 500, "end"))
    y += len(nxt[:4]) * (rh + gap) + 40
    if land:   # prior outlook goes in the right-hand column
        x0 = P + cw + 120
        cw = W - P - x0
        y = top

    # did they deliver last quarter's outlook
    pri = (g.get("prior") or {}).get("items") or []
    pri = [p for p in pri if p.get("actual") is not None][:3]
    room = max(0, (foot_y - 10 - (y + 50)) // prh)   # rows that fit above the footnote
    pri = pri[:room]
    if pri:
        c.add(text(x0, y + 6, f'{l["kept"]} · {g["prior"].get("period", "")}', 24, t["ink"], 700))
        y += 50
        for it in pri:
            lo, hi, act = it["low"], it["high"], it["actual"]
            span = max(hi, act) - min(lo, act)
            pad = span * 0.35 if span else abs(act) * 0.05
            vmin, vmax = min(lo, act) - pad, max(hi, act) + pad
            sx = lambda v: x0 + 260 + (cw - 260 - 40) * (v - vmin) / (vmax - vmin)
            c.add(text(x0, y + 34, it["metric"], 24, t["ink"], 600))
            state = "beat" if act > hi + 1e-12 else ("miss" if act < lo - 1e-12 else "inline")
            if it.get("lower_is_better"):
                good = state != "beat"
            else:
                good = state != "miss"
            col = t["sub"] if state == "inline" else (t["up"] if good else t["down"])
            c.add(text(x0, y + 66, l[state], 20, col, 700))
            # range band + actual marker
            bx0, bx1 = sx(lo), sx(hi)
            c.rect(x0 + 260, y + 30, cw - 300, 4, t["faint"], 2)
            band = t.get("band", t["bar"])
            c.rect(bx0, y + 18, max(bx1 - bx0, 6), 28, band, 6)
            ax = sx(act)
            c.add(f'<circle cx="{ax:.1f}" cy="{y+32}" r="11" fill="{t["ink"]}"/>')
            c.add(text(ax, y + 2, f'{l["actual"]} {_gfmt(act, it, lang)}', 20, t["ink"], 800, "middle"))
            c.add(text(bx0, y + 72, _gfmt(lo, it, lang), 18, t["sub"], 500, "middle"))
            if bx1 - bx0 > 90:
                c.add(text(bx1, y + 72, _gfmt(hi, it, lang), 18, t["sub"], 500, "middle"))
            y += prh
    note = g.get("note")
    foot = l["g_src"] + (f" · {note}" if note else "")
    for i, line in enumerate(wrap(foot, W - 2 * P, 19, 500)):
        c.add(text(P, foot_y + i * 26, line, 19, t["sub"], 500))
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


# ---------- extra templates: poster, post, income, yoy, score ----------
L_EXTRA = {
    "zh": dict(is_t="完整利润表", is_sub="{cur} 对比 {prev}，单位：美元", col_item="项目", col_cur="本期", col_share="占营收",
               col_prev="去年同期", col_yoy="同比", yoy_t="和去年同期比", yoy_sub="{cur} 对比 {prev}",
               last_year="去年同期", score_t="成绩单", vs_guide="对比管理层上一期给的指引（{p}）",
               vs_prev_q="对比上一季度（截至 {e}）", vs_prev_y="对比上一财年（{p}）",
               score_guide="项达到或超过指引", score_better="项比{w}更好", w_q="上一季", w_y="上一财年",
               col_base_g="指引", col_base_q="上一季", col_base_y="上一财年", col_act="本期",
               better="变好", worse="变差", flat="持平", g_above="超出", g_within="区间内", g_below="低于",
               no_consensus="这里比的是公司自己的数据，不是市场一致预期，不代表“超预期”或“不及预期”。",
               post_head="${tk} {fl} 财报：", post_tags="#美股财报 ${tk}", fcf_short="自由现金流",
               p_rev="营收 {v}，同比 {y}", p_gm="毛利率 {v}，同比 {y}", p_ni="净利润 {v}，同比 {y}",
               p_eps="稀释每股收益 {v}，同比 {y}", p_fcf="自由现金流 {v}", poster_more="{gm} {gmv} · {ni} {niv} · {eps} {epsv}",
               eps_short="每股收益"),
    "en": dict(is_t="Income statement", is_sub="{cur} vs {prev}, in US dollars", col_item="Item", col_cur="This period",
               col_share="% rev", col_prev="Year ago", col_yoy="YoY", yoy_t="This year vs last year",
               yoy_sub="{cur} vs {prev}", last_year="Year ago", score_t="Scorecard",
               vs_guide="Against management's prior outlook ({p})", vs_prev_q="Against the previous quarter (ended {e})",
               vs_prev_y="Against the previous fiscal year ({p})", score_guide="met or beat the outlook",
               score_better="better than {w}", w_q="last quarter", w_y="last year",
               col_base_g="Outlook", col_base_q="Last qtr", col_base_y="Last year", col_act="Actual",
               better="Better", worse="Worse", flat="Flat", g_above="Above", g_within="Within", g_below="Below",
               no_consensus="Compared with the company's own numbers, not analyst consensus: this is not a beat or miss vs Street estimates.",
               post_head="${tk} {fl} earnings:", post_tags="#earnings ${tk}", fcf_short="FCF",
               p_rev="Revenue {v}, {y} YoY", p_gm="Gross margin {v}, {y} YoY", p_ni="Net income {v}, {y} YoY",
               p_eps="Diluted EPS {v}, {y} YoY", p_fcf="Free cash flow {v}", poster_more="{gm} {gmv} · {ni} {niv} · {eps} {epsv}",
               eps_short="EPS"),
}


def _lx(l, lang):
    x = dict(L_EXTRA[lang])
    x.update(l)
    return x


def prev_label(d):
    """FY2026 Q2 -> FY2025 Q2 (the same period a year earlier)."""
    m = re.match(r"FY(\d{4})(.*)", d.get("fiscal_label") or "")
    if not m:
        e = d["period_end"]
        return f"{int(e[:4]) - 1}{e[4:]}"
    return f"FY{int(m.group(1)) - 1}{m.group(2)}"


def prev_of(d):
    """The same figures a year earlier: d["prev"] when the data has it, else rebuilt from the trend."""
    if d.get("prev"):
        return d["prev"]
    lag = 1 if is_annual(d) else 4
    tr = d.get("trend") or []
    if len(tr) < lag + 1:
        return {}
    q = tr[-1 - lag]
    out = {k: q.get(k) for k in ("revenue", "net_income", "gross_margin", "operating_margin", "net_margin", "fcf")}
    if q.get("operating_margin") is not None and q.get("revenue"):
        out["operating_income"] = q["operating_margin"] * q["revenue"]
    if q.get("gross_margin") is not None and q.get("revenue"):
        out["gross_profit"] = q["gross_margin"] * q["revenue"]
        out["cost_of_revenue"] = q["revenue"] - out["gross_profit"]
    if d.get("eps") is not None and d.get("eps_yoy") not in (None, -1):
        out["eps"] = d["eps"] / (1 + d["eps_yoy"])
    return {k: v for k, v in out.items() if v is not None}


def prev_seq(d):
    """The previous period (quarter, or year for annual data)."""
    if is_annual(d):
        return prev_of(d)
    if d.get("prev_q"):
        return d["prev_q"]
    tr = d.get("trend") or []
    if len(tr) < 2:
        return {}
    q = tr[-2]
    out = {k: q.get(k) for k in ("revenue", "net_income", "gross_margin", "operating_margin", "net_margin", "fcf")}
    return {k: v for k, v in out.items() if v is not None}


def cur_vals(d):
    gp = d["revenue"] - d["cost_of_revenue"] if d.get("cost_of_revenue") is not None else None
    ni, rev = d.get("net_income"), d.get("revenue")
    return {"revenue": rev, "cost_of_revenue": d.get("cost_of_revenue"), "gross_profit": gp,
            "gross_margin": d.get("gross_margin"), "rnd": d.get("rnd"), "sga": d.get("sga"),
            "operating_income": d.get("operating_income"), "operating_margin": d.get("operating_margin"),
            "tax": d.get("tax"), "net_income": ni, "net_margin": ni / rev if ni is not None and rev else None,
            "eps": d.get("eps"), "fcf": d.get("fcf")}


def _fmt(k, v, lang):
    if v is None:
        return "—"
    if k.endswith("margin"):
        return pct(v, False)
    if k == "eps":
        return ("−" if v < 0 else "") + f"${abs(v):.2f}"
    return money(v, lang)


def _change(k, cur, prev, l):
    """(text, value) of the change from prev to cur: pts for margins, % otherwise. None when not comparable."""
    if cur is None or prev is None:
        return None
    if k.endswith("margin"):
        dv = (cur - prev) * 100
        return f'{dv:+.1f} {l["pts"]}'.replace("-", "−"), dv / 100
    if not prev:
        return None
    dv = (cur - prev) / abs(prev)
    return pct(dv), dv


def top_bar(c, d, l, P):
    """Ticker, company and period across the top with a rule under it; returns the rule's y."""
    t = c.t
    right = f'{d.get("fiscal_label","")} · {l["ended"]} {d["period_end"]}'
    ts, cs, rs, y, ry = (30, 20, 18, 100, 122) if c.h <= 1080 else (34, 22, 20, 112, 140)
    tw = measure(d["ticker"], ts, 800, -0.5)
    room = c.w - 2 * P - tw - 16 - measure(right, rs, 500) - 24
    c.add(text(P, y, d["ticker"], ts, t["ink"], 800, ls=-0.5))
    c.add(text(P + tw + 16, y, clip(company_name(d), room, cs, 500), cs, t["sub"], 500))
    c.add(text(c.w - P, y, right, rs, t["sub"], 500, "end"))
    c.rect(P, ry, c.w - 2 * P, 2, t["ink"])
    return ry


def arrow(c, x, y, up, size, color):
    """A small filled triangle; (x, y) is its left edge at the text baseline."""
    h = size * 0.62
    w = size * 0.7
    if up:
        pts = f"{x:.1f},{y:.1f} {x + w:.1f},{y:.1f} {x + w / 2:.1f},{y - h:.1f}"
    else:
        pts = f"{x:.1f},{y - h:.1f} {x + w:.1f},{y - h:.1f} {x + w / 2:.1f},{y:.1f}"
    c.add(f'<polygon points="{pts}" fill="{color}"/>')
    return w


def card_poster(d, l, lang, t, headline, size=None):
    """One number, as big as it gets: revenue and its YoY change."""
    W, H = size or (1080, 1350)
    P = 80
    x = _lx(l, lang)
    c = Card(W, H, t)
    y0 = top_bar(c, d, l, P)
    land, square = W > H, W == H
    rv = money(d["revenue"], lang)
    S = fit(rv, W - 2 * P, 230 if land else (200 if square else 250), 800, -6, floor=60)
    yoy = d.get("revenue_yoy")
    ys = f'{pct(yoy)} {l["yoy"]}' if yoy is not None else ""
    ysz = 56 if not square else 48
    hs = 42 if not square else 36
    with display_font():
        lines = wrap(headline, W - 2 * P, hs, 700) if headline else []
    eps = "—" if d.get("eps") is None else f'${d["eps"]:.2f}'
    more = x["poster_more"].format(gm=l["gm"], gmv=pct(d.get("gross_margin"), False), ni=l["ni"],
                                   niv=money(d.get("net_income"), lang), eps=x["eps_short"], epsv=eps)
    msz = fit(more, W - 2 * P, 26 if not square else 24, 500, floor=16)
    # stack the block, then centre it vertically between the top rule and the footer rule
    items, y = [], 0
    for line in lines:
        y += hs
        items.append(("h", line, y, hs, t["ink"], 700))
        y += round(hs * 0.32)
    if lines:
        y += 44
    items.append(("bar", None, y, 0, t.get("hi", t["ink"]), 0))
    y += 8 + 58
    items.append(("t", l["rev"], y, 30, t["sub"], 500))
    y += round(0.2 * 30 + 0.74 * S + 28)
    items.append(("t", rv, y, S, t["ink"], 800))
    if ys:
        y += round(0.2 * S + 36 + 0.74 * ysz)
        items.append(("t", ys, y, ysz, t["up"] if yoy >= 0 else t["down"], 800))
    y += round(0.2 * ysz + 44 + 0.74 * msz)
    items.append(("t", more, y, msz, t["sub"], 500))
    block = y + round(0.2 * msz)
    top, bottom = y0 + 40, H - 94 - 40
    off = top + max(0, (bottom - top - block) // 2)
    for kind, s_, yy, sz, col, wt in items:
        if kind == "bar":
            c.rect(W / 2 - 40, off + yy, 80, 8, col, 2)
        elif kind == "h":
            with display_font():
                c.add(text(W / 2, off + yy, s_, sz, col, wt, "middle"))
        else:
            c.add(text(W / 2, off + yy, s_, sz, col, wt, "middle", ls=-6 if sz == S else 0))
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def post_lines(d, l, lang, x):
    """The text of the social-post card, one bullet per line (no invented numbers)."""
    tk, fl = d["ticker"], d.get("fiscal_label") or d["period_end"]
    out = [("head", x["post_head"].replace("${tk}", "$" + tk).format(fl=fl))]
    if d.get("revenue_yoy") is not None:
        out.append(("b", x["p_rev"].format(v=money(d["revenue"], lang), y=pct(d["revenue_yoy"]))))
    if d.get("gross_margin") is not None and d.get("gross_margin_prev") is not None:
        dv = (d["gross_margin"] - d["gross_margin_prev"]) * 100
        out.append(("b", x["p_gm"].format(v=pct(d["gross_margin"], False), y=f'{dv:+.1f} {l["pts"]}'.replace("-", "−"))))
    if d.get("net_income") is not None and d.get("net_income_yoy") is not None:
        out.append(("b", x["p_ni"].format(v=money(d["net_income"], lang), y=pct(d["net_income_yoy"]))))
    if d.get("eps") is not None and d.get("eps_yoy") is not None:
        out.append(("b", x["p_eps"].format(v=f'${d["eps"]:.2f}', y=pct(d["eps_yoy"]))))
    if d.get("fcf") is not None:
        out.append(("b", x["p_fcf"].format(v=money(d["fcf"], lang))))
    out.append(("tag", x["post_tags"].replace("${tk}", "$" + tk)))
    return out


def card_post(d, l, lang, t, headline, size=None):
    """Looks like a post on X / Weibo: avatar, name, a short summary of the period and a small chart."""
    W, H = size or (1080, 1350)
    P = 80 if W <= 1080 else 120
    x = _lx(l, lang)
    c = Card(W, H, t)
    land, square = W > H, W == H
    py0, py1 = (70, H - 120) if not square else (60, H - 116)
    c.box(P, py0, W - 2 * P, py1 - py0, 28)
    ix, iw = P + 44, W - 2 * P - 88
    # author row
    handle = (t.get("handle") or "").strip()
    name = handle.lstrip("@") or "earnings-card"
    at = ("@" + handle.lstrip("@")) if handle else "@earnings-card"
    r = 34 if square else 38
    cx, cy = ix + r, py0 + 40 + r
    if t.get("avatar"):
        _AV[0] += 1
        cid = f"pav{_AV[0]}"
        c.add(f'<clipPath id="{cid}"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>'
              f'<image href="{t["avatar"]}" x="{cx - r}" y="{cy - r}" width="{2 * r}" height="{2 * r}" '
              f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{cid})"/>')
    else:
        c.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{t.get("hi", t["ink"])}"/>')
        ini = (name[:1] or "e").upper()
        c.add(text(cx, cy + 12, ini, 34, t["bg"], 800, "middle"))
    nx = ix + 2 * r + 20
    nroom = ix + iw - nx - 60
    c.add(text(nx, cy - 6, clip(name, nroom, 30, 800), 30, t["ink"], 800))
    sub = f'{at} · {d["filed"]}'
    c.add(text(nx, cy + 28, clip(sub, nroom, 22, 500), 22, t["sub"], 500))
    for k in range(3):   # the "more" dots
        c.add(f'<circle cx="{ix + iw - 8 - k * 14}" cy="{cy - 12}" r="3.5" fill="{t["sub"]}"/>')
    # post text
    fs = 36 if H > 1350 else (28 if square else 32)
    lh = round(fs * 1.5)
    tx_w = iw * 0.5 if land else iw
    y = cy + r + 34
    rows = []
    for kind, s_ in post_lines(d, l, lang, x):
        if kind == "head" and headline:
            rows.append((s_, t["ink"], 700))
            for line in wrap(headline, tx_w, fs, 700):
                rows.append((line, t["ink"], 700))
            continue
        if kind == "b":
            s_ = "· " + s_
        col, wt = (t.get("hi", t["ink"]), 600) if kind == "tag" else (t["ink"], 700 if kind == "head" else 400)
        rows.append((s_, col, wt))
    max_rows = max(3, int((py1 - 120 - y) // lh)) if land else len(rows)
    if len(rows) > max_rows:
        rows = rows[:max_rows - 1] + rows[-1:]
    for s_, col, wt in rows:
        y += lh
        sz = fit(s_, tx_w, fs, wt, floor=18)
        c.add(text(ix, y - round(fs * 0.35), clip(s_, tx_w, sz, wt), sz, col, wt))
    # media: a small revenue chart
    act_y = py1 - 56
    if land:
        mx, mw, my, mh = ix + iw * 0.55, iw * 0.45, cy + r + 34, act_y - 30 - (cy + r + 34)
    else:
        mx, mw, my, mh = ix, iw, y + 24, act_y - 30 - (y + 24)
    if mh >= 170:
        c.rect(mx, my, mw, mh, t["bg"], 20, f'stroke="{t["faint"]}" stroke-width="1.5"')
        c.add(text(mx + 28, my + 44, l["trend"].format(n=len(d["trend"])), 20, t["sub"], 500))
        bars(c, mx + 28, my + 58, mw - 56, mh - 58 - 54, [q["revenue"] for q in d["trend"]],
             [plabel(q) for q in d["trend"]], lang)
    # action row: reply, repost, like, share (icons only, no made-up counts)
    c.rect(ix, act_y - 4, iw, 1.5, t["faint"])
    sw = f'fill="none" stroke="{t["sub"]}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"'
    ay = act_y + 28
    xs = [ix + 10 + iw * k / 4 for k in range(4)]
    c.add(f'<path d="M{xs[0]:.1f},{ay - 11} h22 a6,6 0 0 1 6,6 v10 a6,6 0 0 1 -6,6 h-12 l-8,7 v-7 h-2 a6,6 0 0 1 -6,-6 v-10 a6,6 0 0 1 6,-6 z" {sw}/>')
    c.add(f'<path d="M{xs[1]:.1f},{ay - 2} v-6 h20 l-5,-5 M{xs[1] + 30:.1f},{ay + 2} v6 h-20 l5,5" {sw}/>')
    hx = xs[2] + 14
    c.add(f'<path d="M{hx:.1f},{ay + 12} l-12,-12 a7,7 0 0 1 12,-9 a7,7 0 0 1 12,9 z" {sw}/>')
    c.add(f'<path d="M{xs[3] + 12:.1f},{ay + 10} v-22 l-8,8 M{xs[3] + 12:.1f},{ay - 12} l8,8" {sw}/>')
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


INCOME_ROWS = [("rev", "revenue", True), ("cost", "cost_of_revenue", False), ("gp", "gross_profit", True),
               ("rnd", "rnd", False), ("sga", "sga", False), ("oi", "operating_income", True),
               ("tax", "tax", False), ("ni", "net_income", True), ("eps", "eps", True)]
COSTS = {"cost_of_revenue", "rnd", "sga", "tax"}


def card_income(d, l, lang, t, size=None):
    """The income statement from revenue down to EPS, with the year-ago figures and the YoY change."""
    W, H = size or (1080, 1350)
    P = 80
    x = _lx(l, lang)
    c = Card(W, H, t)
    cur_fl = d.get("fiscal_label") or d["period_end"]
    y = small_header(c, d, l, x["is_t"], x["is_sub"].format(cur=cur_fl, prev=prev_label(d)), P)
    cur, prev = cur_vals(d), prev_of(d)
    rows = [(l[k], key, total) for k, key, total in INCOME_ROWS if cur.get(key) is not None]
    iw = W - 2 * P
    ends = [P + iw * f for f in ((0.52, 0.65, 0.85, 1.0) if W <= 1080 else (0.5, 0.62, 0.83, 1.0))]
    item_w = iw * (0.30 if W <= 1080 else 0.36)
    hy = y + 14
    hsz = 18
    c.add(text(P, hy, x["col_item"], hsz, t["sub"], 600))
    for e_, lab in zip(ends, (x["col_cur"], x["col_share"], x["col_prev"], x["col_yoy"])):
        c.add(text(e_, hy, lab, hsz, t["sub"], 600, "end"))
    c.rect(P, hy + 16, iw, 2, t["ink"])
    top = hy + 18
    bottom = H - 150
    rh = min(124 if H > 1350 else 84, (bottom - top) / max(len(rows), 1))
    col_w = (ends[0] - P - item_w - 20)
    for i, (lab, key, total) in enumerate(rows):
        ry = top + i * rh
        base = round(ry + rh / 2 + 9)
        if total and key not in ("revenue", "eps"):
            c.rect(P, ry, iw, rh, t["card"], 0, f'fill-opacity="{t.get("card_opacity", 1)}"')
        lsz, vsz, vw = (24, 26, 800) if total else (22, 23, 600)
        c.add(text(P + (0 if total else 18), base, clip(lab, item_w - (0 if total else 18), lsz, 700 if total else 500),
                   lsz, t["ink"] if total else t["sub"], 700 if total else 500))
        cv, pv = cur.get(key), prev.get(key)
        vs = _fmt(key, cv, lang)
        c.add(text(ends[0], base, vs, fit(vs, col_w, vsz, vw, floor=14), t["ink"], vw, "end"))
        if key != "eps" and d.get("revenue"):
            sh = f'{cv / d["revenue"] * 100:.1f}%'
            c.add(text(ends[1], base, sh, 19, t["sub"], 500, "end"))
        ps = _fmt(key, pv, lang)
        c.add(text(ends[2], base, ps, fit(ps, ends[2] - ends[1] - 24, 22, 500, floor=14), t["sub"], 500, "end"))
        ch = _change(key, cv, pv, l)
        if ch:
            good = ch[1] >= 0 if key not in COSTS else None
            col = t["sub"] if good is None else (t["up"] if good else t["down"])
            c.add(text(ends[3], base, ch[0], fit(ch[0], ends[3] - ends[2] - 20, 21, 700, floor=14), col, 700, "end"))
        else:
            c.add(text(ends[3], base, "—", 21, t["sub"], 500, "end"))
        c.rect(P, ry + rh - 1, iw, 1, t["faint"])
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


YOY_METRICS = [("rev", "revenue"), ("gm", "gross_margin"), ("om", "operating_margin"), ("ni", "net_income"),
               ("eps", "eps"), ("fcf", "fcf")]


def card_yoy(d, l, lang, t, size=None):
    """This period next to the same period a year earlier, six metrics with arrows."""
    W, H = size or (1080, 1350)
    P = 80
    x = _lx(l, lang)
    c = Card(W, H, t)
    cur_fl, prev_fl = d.get("fiscal_label") or d["period_end"], prev_label(d)
    y = small_header(c, d, l, x["yoy_t"], x["yoy_sub"].format(cur=cur_fl, prev=prev_fl), P)
    cur, prev = cur_vals(d), prev_of(d)
    items = [(l[k], key) for k, key in YOY_METRICS if cur.get(key) is not None and prev.get(key) is not None][:6]
    cols = 2 if W < H else 3
    nrow = max(1, -(-len(items) // cols))
    g = 18
    top, bottom = y, H - 130
    cw = (W - 2 * P - g * (cols - 1)) / cols
    ch = min((bottom - top - g * (nrow - 1)) / nrow, 420)
    vs0 = 46 if ch < 300 else 60
    for i, (lab, key) in enumerate(items):
        bx, by = P + (i % cols) * (cw + g), top + (i // cols) * (ch + g)
        c.box(bx, by, cw, ch, 18)
        inner = cw - 52
        cv, pv = cur[key], prev[key]
        c.add(text(bx + 26, by + 44, clip(lab, inner, 22, 600), 22, t["sub"], 600))
        val = _fmt(key, cv, lang)
        vs = fit(val, inner, vs0, 800, -1)
        vy = round(by + 44 + 18 + vs0 * 0.95)
        c.add(text(bx + 26, vy, val, vs, t["ink"], 800, ls=-1))
        ps = f'{x["last_year"]} {_fmt(key, pv, lang)}'
        py = vy + 44
        c.add(text(bx + 26, py, ps, fit(ps, inner, 21, 500, floor=14), t["sub"], 500))
        chg = _change(key, cv, pv, l)
        dy = py + 44
        if chg:
            up = chg[1] >= 0
            col = t["up"] if up else t["down"]
            aw = arrow(c, bx + 26, dy, up, 24, col)
            c.add(text(bx + 26 + aw + 10, dy, chg[0], fit(chg[0], inner - aw - 10, 24, 800, floor=14), col, 800))
        # paired bars: year ago (light) and now (strong), on one scale
        bb = by + ch - 26
        if bb - dy > 48:
            mx = max(abs(cv), abs(pv)) or 1
            for k, (v, colr) in enumerate(((pv, t["bar"]), (cv, t.get("hi", t["ink"]) if cv >= 0 else t["down"]))):
                c.rect(bx + 26, bb - 12 - (1 - k) * 20, max(inner * abs(v) / mx, 3), 12, colr, 3)
    if not items:
        c.add(text(P, y + 40, "—", 28, t["sub"], 500))
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


SCORE_METRICS = [("rev", "revenue"), ("gm", "gross_margin"), ("om", "operating_margin"), ("ni", "net_income"),
                 ("eps", "eps"), ("fcf", "fcf")]


def _seq_rows(d, l, lang, x):
    cur, prev = cur_vals(d), prev_seq(d)
    rows = []
    for k, key in SCORE_METRICS:
        cv, pv = cur.get(key), prev.get(key)
        ch = _change(key, cv, pv, l)
        if ch is None:
            continue
        thr = 0.001 if key.endswith("margin") else 0.005
        state = "flat" if abs(ch[1]) < thr else ("better" if ch[1] > 0 else "worse")
        rows.append((l[k], _fmt(key, pv, lang), _fmt(key, cv, lang), state, state == "better"))
    if is_annual(d):
        return rows, x["vs_prev_y"].format(p=prev_label(d)), x["score_better"].format(w=x["w_y"]), x["col_base_y"]
    tr = d.get("trend") or []
    e = tr[-2]["end"] if len(tr) > 1 else ""
    return rows, x["vs_prev_q"].format(e=e), x["score_better"].format(w=x["w_q"]), x["col_base_q"]


def score_sections(d, l, lang, g):
    """[(basis, score label, base column title, rows)]; rows = (metric, base, actual, verdict key, good).

    With a matching outlook the first section is actual vs that outlook (and the previous quarter follows
    when there is room); otherwise it is actual vs the previous quarter / fiscal year."""
    x = _lx(l, lang)
    pri = [p for p in ((g or {}).get("prior") or {}).get("items") or [] if p.get("actual") is not None]
    seq = _seq_rows(d, l, lang, x)
    out = []
    if pri and not is_annual(d):
        rows = []
        for it in pri[:6]:
            lo, hi, act = it["low"], it["high"], it["actual"]
            state = "above" if act > hi + 1e-12 else ("below" if act < lo - 1e-12 else "within")
            good = state != "above" if it.get("lower_is_better") else state != "below"
            rows.append((it["metric"], _grange(it, lang), _gfmt(act, it, lang), "g_" + state, good))
        out.append((x["vs_guide"].format(p=g["prior"].get("period", "")), x["score_guide"], x["col_base_g"], rows))
        if len(rows) <= 3 and seq[0]:
            out.append((seq[1], seq[2], seq[3], seq[0][:6 - len(rows)]))
        return out
    return [(seq[1], seq[2], seq[3], seq[0])]


def card_score(d, l, lang, t, g=None, size=None):
    """Beat / miss scoreboard against the company's own last outlook, or else against the previous period.
    Never against analyst consensus (there is none in the data); the card says what it compares."""
    W, H = size or (1080, 1350)
    P = 80
    x = _lx(l, lang)
    c = Card(W, H, t)
    secs = score_sections(d, l, lang, g)
    basis, score_lab, _, rows0 = secs[0]
    good = sum(1 for r in rows0 if r[4])
    y = small_header(c, d, l, x["score_t"], basis, P)
    land, square = W > H, W == H
    ss = 120 if not square else 96
    sc = f"{good}/{len(rows0)}"
    c.add(text(P - 4, y + round(ss * 0.8), sc, ss, t.get("hi", t["ink"]), 800, ls=-4))
    lx = P + measure(sc, ss, 800, -4) + 28
    lroom = (W - P - lx) if not land else (P + 600 - lx)
    c.add(text(lx, y + round(ss * 0.8) - 6, clip(score_lab, lroom, 28, 700), fit(score_lab, lroom, 28, 700, floor=18), t["ink"], 700))
    if land:   # rows on the right, score and note on the left
        rx0, rx1, ry0 = P + 680, W - P, y - 10
        note_x, note_w, note_y = P, 560, y + ss + 60
    else:
        rx0, rx1, ry0 = P, W - P, y + ss + 50
        note_x, note_w, note_y = P, W - 2 * P, H - 168
    rw = rx1 - rx0
    ends = [rx0 + rw * 0.56, rx0 + rw * 0.80, rx1]
    bottom = (H - 150) if land else note_y - 40
    nrows = sum(len(sec[3]) for sec in secs)
    sec_head = 56   # a later section's title line + column header
    rh = min(96 if H <= 1350 else 128, (bottom - ry0 - 16 * len(secs) - sec_head * (len(secs) - 1)) / max(nrows, 1))
    yy = ry0
    for si, (sb, _, colb, rows) in enumerate(secs):
        if si:
            yy += 34
            c.add(text(rx0, yy, clip(sb, rw, 20, 700), 20, t["ink"], 700))
            yy += 22 + 14
        c.add(text(rx0, yy, x["col_item"], 18, t["sub"], 600))
        c.add(text(ends[0], yy, colb, 18, t["sub"], 600, "end"))
        c.add(text(ends[1], yy, x["col_act"], 18, t["sub"], 600, "end"))
        c.rect(rx0, yy + 14, rw, 2, t["ink"])
        top = yy + 16
        for i, (lab, base, act, state, ok) in enumerate(rows):
            ry = top + i * rh
            b = round(ry + rh / 2 + 9)
            c.add(text(rx0, b, clip(lab, rw * 0.30, 24, 600), 24, t["ink"], 600))
            bw = ends[0] - rx0 - rw * 0.32
            c.add(text(ends[0], b, base, fit(base, bw, 22, 500, floor=13), t["sub"], 500, "end"))
            c.add(text(ends[1], b, act, fit(act, ends[1] - ends[0] - 20, 24, 800, floor=14), t["ink"], 800, "end"))
            col = t["sub"] if state == "flat" else (t["up"] if ok else t["down"])
            psz = 18 if rh < 70 else 20
            pill(c, ends[2], round(ry + rh / 2 - psz * 1.05), x[state], psz, col)
            c.rect(rx0, ry + rh - 1, rw, 1, t["faint"])
        yy = top + len(rows) * rh
    for i, line in enumerate(wrap(x["no_consensus"], note_w, 19, 500, 4)):
        c.add(text(note_x, note_y + i * 26, line, 19, t["sub"], 500))
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


CARDS = {"cover": card_cover, "mix": card_mix, "guide": card_guide, "profit": card_profit, "trend": card_trend, "cash": card_cash, "wide": card_wide,
         "poster": card_poster, "post": card_post, "income": card_income, "yoy": card_yoy, "score": card_score}
EXTRA_CARDS = ["poster", "post", "income", "yoy", "score"]


def page(svgs, title):
    imgs = "\n".join(svgs)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;padding:40px 0;display:flex;flex-direction:column;align-items:center;gap:32px;background:#e9e6df}}
svg{{width:min(92vw,540px);height:auto;box-shadow:0 1px 3px rgba(0,0,0,.1)}}svg[width="1600"],svg[width="1920"]{{width:min(92vw,800px)}}</style></head>
<body>{imgs}</body></html>"""


def card_names(d, cards=None, ratio="4:5", guidance=None):
    """The cards render_cards() will draw, in order: the requested ones minus those without data."""
    size = RATIOS[ratio]
    names = [n for n in (cards or DEFAULT_CARDS) if n in CARDS]
    if not (d.get("segments") or {}) and "mix" in names:
        names.remove("mix")
    if (is_annual(d) or not (guidance and (guidance.get("next") or {}).get("items"))) and "guide" in names:
        names.remove("guide")
    for n in ("income", "yoy"):
        if n in names and not prev_of(d):
            names.remove(n)
    if size[0] > size[1] and "cover" in names and "wide" in names:
        names.remove("wide")
    return names


def render_cards(d, lang="zh", style="light", cards=None, ratio="4:5", headline="", guidance=None, labels=None, only=None):
    """Render a card set and return [(name, svg)]. Used by the CLI below and by the web app (via Pyodide).

    style: a built-in name, a style JSON path, or a dict from build_style().
    Cards without data are left out: mix without segments, guide without guidance (and always for annual data);
    at 16:9 the cover already is the landscape layout, so wide is dropped (see card_names()).
    only: indexes into card_names() to draw just those cards (page numbers stay those of the full set)."""
    global CURRENT_PAGE
    t = style if isinstance(style, dict) else resolve_style(style)
    l = labels_for(lang, d.get("period"))
    size = RATIOS[ratio]
    names = card_names(d, cards, ratio, guidance)
    portrait = [n for n in names if n != "wide"]
    out = []
    for i, name in enumerate(names):
        if only is not None and i not in only:
            continue
        fn = CARDS[name]
        CURRENT_PAGE = f"{portrait.index(name) + 1}/{len(portrait)}" if name in portrait and len(portrait) > 1 else ""
        if name == "wide":
            svg = fn(d, l, lang, t, headline)
        elif name in ("cover", "poster", "post"):
            svg = fn(d, l, lang, t, headline, size=size)
        elif name == "mix":
            svg = fn(d, l, lang, t, labels or {}, size=size)
        elif name in ("guide", "score"):
            svg = fn(d, l, lang, t, guidance, size=size)
        else:
            svg = fn(d, l, lang, t, size=size)
        out.append((name, svg))
    CURRENT_PAGE = ""
    return out


def web_render(data_json, opts_json):
    """Entry point for the browser: JSON in, JSON out ([{name, svg, w, h}]).

    opts: lang, style (built-in name), font (auto|sans|serif|mono), bg / ink / hi (optional colours),
          handle, avatar (data URI), ratio, cards, headline, guidance, labels."""
    d, o = json.loads(data_json), json.loads(opts_json)
    d = period_record(d, o.get("period_end"))
    custom = {"base": o.get("style") or "light", "font": o.get("font") or "auto"}
    if o.get("handle"):
        custom["handle"] = o["handle"]
    if o.get("avatar"):
        custom["avatar"] = o["avatar"]
    t = recolor(build_style(custom), o.get("bg"), o.get("ink"), o.get("hi"), o.get("a2"), o.get("updown"))
    only = o.get("only")
    if isinstance(only, int):
        only = [only]
    res = render_cards(d, o.get("lang") or "zh", t, o.get("cards"), o.get("ratio") or "4:5",
                       o.get("headline") or "", o.get("guidance"), o.get("labels"), only)
    out = []
    for name, svg in res:
        m = re.search(r'width="(\d+)" height="(\d+)"', svg)
        out.append({"name": name, "svg": svg, "w": int(m.group(1)), "h": int(m.group(2))})
    if only is not None:   # one card of a set: also say what the whole set is, for progress and placeholders
        names = card_names(d, o.get("cards"), o.get("ratio") or "4:5", o.get("guidance"))
        return json.dumps({"names": names, "cards": out}, ensure_ascii=False)
    return json.dumps(out, ensure_ascii=False)


# ---------- share text: a caption and headline ideas, from the numbers only ----------
CAP = {
    "zh": dict(q="季报", a="年报", ended="截至", yoy="同比", up="增长", down="下降", pts="个百分点",
               eps="稀释 EPS", src="数据：SEC EDGAR {form}（GAAP）· 不构成投资建议", tags="#{tk} {zh}#美股 #财报",
               doubled="营收同比翻倍以上，达 {v}", rev="营收 {v}，同比{dir} {p}", ni="净利润 {v}，同比{dir} {p}",
               ni_turn="扭亏为盈，净利润 {v}", eps_h="稀释 EPS {v}，同比{dir} {p}", gm="毛利率 {v}，同比{dir} {p} 个百分点", gm_up="提升", rec_tail="，创近 {n} {per}新高",
               om="营业利润率 {v}", rec="营收 {v}，创近 {n} {per}新高", per_q="个季度", per_a="个财年", fcf="自由现金流 {v}"),
    "en": dict(q="quarterly results", a="annual results", ended="period ended", yoy="YoY", up="up", down="down", pts="pts",
               eps="Diluted EPS", src="Data: SEC EDGAR {form} (GAAP) · Not investment advice", tags="#{tk} #earnings #stocks",
               doubled="Revenue more than doubled YoY to {v}", rev="Revenue {dir} {p} YoY to {v}", ni="Net income {dir} {p} YoY to {v}",
               ni_turn="Back to profit: net income of {v}", eps_h="EPS {dir} {p} YoY to {v}", gm="Gross margin {v}, {dir} {p} pts YoY", gm_up="up", rec_tail=", the highest in {n} {per}",
               om="Operating margin of {v}", rec="Revenue of {v}, the highest in {n} {per}", per_q="quarters", per_a="years",
               fcf="Free cash flow of {v}"),
}


def _eps(v):
    return ("−" if v < 0 else "") + f"${abs(v):.2f}"


def caption(d, lang="zh", name_zh=""):
    """A plain-text post caption: period, revenue + YoY, margins, net income, EPS, FCF, source, hashtags.
    Every figure comes from d and uses the same money()/pct() formatting as the cards."""
    k, l = CAP[lang], labels_for(lang, d.get("period"))
    tk, rev = d["ticker"], d.get("revenue")
    name = name_zh if (lang == "zh" and name_zh) else company_name(d)
    kind = k["a"] if is_annual(d) else k["q"]
    if lang == "zh":
        lines = [f"{name}（{tk}）{d.get('fiscal_label', '')} {kind}（{k['ended']} {d['period_end']}）"]
    else:
        lines = [f"{name} ({tk}) {d.get('fiscal_label', '')} {kind}, {k['ended']} {d['period_end']}"]
    sep = "，" if lang == "zh" else ", "
    if rev is not None:
        s = f"{l['rev']} {money(rev, lang)}"
        if d.get("revenue_yoy") is not None:
            s += f"{sep}{k['yoy']} {pct(d['revenue_yoy'])}"
        lines.append(s)
    ni = d.get("net_income")
    m = [(l["gm"], d.get("gross_margin")), (l["om"], d.get("operating_margin")),
         (l["nm"], ni / rev if ni is not None and rev else None)]
    m = [f"{a} {pct(v, False)}" for a, v in m if v is not None]
    if m:
        lines.append(" · ".join(m))
    if ni is not None:
        s = f"{l['ni']} {money(ni, lang)}"
        if d.get("net_income_yoy") is not None and (prev_of(d).get("net_income") or 0) > 0 and ni > 0:
            s += f"{sep}{k['yoy']} {pct(d['net_income_yoy'])}"
        lines.append(s)
    if d.get("eps") is not None:
        s = f"{k['eps']} {_eps(d['eps'])}"
        if d.get("eps_yoy") is not None and (prev_of(d).get("eps") or 0) > 0 and d["eps"] > 0:
            s += f"{sep}{k['yoy']} {pct(d['eps_yoy'])}"
        lines.append(s)
    if d.get("fcf") is not None:
        lines.append(f"{l['fcf']} {money(d['fcf'], lang)}")
    lines.append(k["src"].format(form=d.get("form", "").replace(" (derived)", "")))
    tag = re.sub(r"[^A-Za-z0-9]", "", tk)
    lines.append(k["tags"].format(tk=tag, zh=f"#{name_zh} " if name_zh else ""))
    return "\n".join(lines)


def headline_ideas(d, lang="zh", n=3):
    """Up to n short headlines, each one fact read straight off the numbers (no outlook, no adjectives
    the data can't back). Strongest first: the biggest relative move wins."""
    k = CAP[lang]
    ideas = []

    def chg(v):
        return ("up" if v >= 0 else "down"), pct(abs(v), False)

    rev, ry = d.get("revenue"), d.get("revenue_yoy")
    tr = [q.get("revenue") for q in (d.get("trend") or []) if q.get("revenue") is not None]
    per = k["per_a" if is_annual(d) else "per_q"]
    record = rev is not None and len(tr) >= 4 and rev >= max(tr)
    if rev is not None and ry is not None:
        if ry >= 1:
            h = k["doubled"].format(v=money(rev, lang))
        else:
            dr, p = chg(ry)
            h = k["rev"].format(v=money(rev, lang), dir=k[dr], p=p)
        tail = k["rec_tail"].format(n=len(tr), per=per) if record else ""
        if tail and len(h + tail) <= 60:   # one revenue headline: the move, and that it is the top of the window
            h, tail = h + tail, ""
        ideas.append((abs(ry) + (0.3 if record else 0), h))
        if tail:
            ideas.append((0.35, k["rec"].format(v=money(rev, lang), n=len(tr), per=per)))
    elif record:
        ideas.append((0.35, k["rec"].format(v=money(rev, lang), n=len(tr), per=per)))
    ni, prev = d.get("net_income"), prev_of(d)
    pni = prev.get("net_income")
    if ni is not None and pni is not None:
        if pni < 0 < ni:
            ideas.append((0.9, k["ni_turn"].format(v=money(ni, lang))))
        elif ni > 0 and pni > 0 and d.get("net_income_yoy") is not None:
            dr, p = chg(d["net_income_yoy"])
            ideas.append((abs(d["net_income_yoy"]) * 0.9, k["ni"].format(v=money(ni, lang), dir=k[dr], p=p)))
    eps, pe = d.get("eps"), prev.get("eps")
    if eps is not None and pe and eps > 0 and pe > 0 and d.get("eps_yoy") is not None:
        dr, p = chg(d["eps_yoy"])
        ideas.append((abs(d["eps_yoy"]) * 0.8, k["eps_h"].format(v=_eps(eps), dir=k[dr], p=p)))
    gm, gp = d.get("gross_margin"), d.get("gross_margin_prev", prev.get("gross_margin"))
    if gm is not None and gp is not None and abs(gm - gp) >= 0.01:
        dv = (gm - gp) * 100
        ideas.append((abs(dv) / 20, k["gm"].format(v=pct(gm, False), dir=k["gm_up" if dv > 0 else "down"], p=f"{abs(dv):.1f}")))
    om = d.get("operating_margin")
    if om is not None and om >= 0.25:
        ideas.append((om / 2, k["om"].format(v=pct(om, False))))
    if d.get("fcf") is not None and d["fcf"] > 0:
        ideas.append((0.05, k["fcf"].format(v=money(d["fcf"], lang))))
    ideas.sort(key=lambda x: -x[0])
    out = []
    for _, h in ideas:
        if h not in out:
            out.append(h)
    return out[:n]


def web_extras(data_json, opts_json):
    """For the browser: {"caption", "headlines"} for one period. opts: lang, period_end, name_zh."""
    d, o = json.loads(data_json), json.loads(opts_json)
    d = period_record(d, o.get("period_end"))
    lang = o.get("lang") or "zh"
    return json.dumps({"caption": caption(d, lang, o.get("name_zh") or ""), "headlines": headline_ideas(d, lang)},
                      ensure_ascii=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", required=True, help="output prefix, e.g. ./NVDA")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--headline", default="")
    ap.add_argument("--theme", "--style", dest="theme", default="light",
                    help="built-in style (light/paper, dark/ink, mono, terminal, salmon, pop, bloomberg, keynote, neon, vintage, "
                         "morandi, glass) or a custom style JSON file")
    ap.add_argument("--ratio", default="4:5", choices=list(RATIOS),
                    help="card shape: 4:5 portrait (default), 1:1 square, 9:16 story, 16:9 landscape")
    ap.add_argument("--cards", default="cover,mix,profit,trend,cash,guide,wide")
    ap.add_argument("--guidance", default="", help="guidance.json written by the agent from fetch_guidance.py output")
    ap.add_argument("--labels", default="", help="JSON file mapping segment labels to display names (e.g. Chinese)")
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--period", default="quarter", choices=["quarter", "annual"],
                    help="for a docs/data/{TICKER}.json file (holds both): which report type")
    ap.add_argument("--period-end", default="", help="pick a period by its end date (YYYY-MM-DD)")
    ap.add_argument("--fy", default="", help="pick a period by fiscal year, e.g. 2026 (with --fq for a quarter)")
    ap.add_argument("--fq", default="", help="fiscal quarter 1-4, with --fy")
    a = ap.parse_args()
    d = json.load(open(a.data))
    if "quarter" in d or "annual" in d:   # a docs/data file: {"quarter": block, "annual": block}
        if not d.get(a.period):
            sys.exit(f"No {a.period} data in {a.data}")
        d = d[a.period]
    if "periods" in d:
        full = period_record(d, a.period_end or None, a.fy or None, a.fq or None)
        if full is None:
            have = ", ".join(p.get("fiscal_label") or p["period_end"] for p in d["periods"])
            sys.exit(f"No such period. Available: {have}")
        d = full
    elif a.period_end or a.fy:
        sys.exit("--period-end / --fy need a multi-period file (docs/data/{TICKER}.json); "
                 "for a fetch_sec.py file, pass the same flags to fetch_sec.py instead")
    labels = json.load(open(a.labels)) if a.labels else {}
    guidance = json.load(open(a.guidance)) if a.guidance else None
    names = [n for n in a.cards.split(",") if n]
    svgs = []
    for i, (name, svg) in enumerate(render_cards(d, a.lang, a.theme, names, a.ratio, a.headline, guidance, labels)):
        svgs.append(svg)
        base = f"{a.out}-{i+1}-{name}"
        open(base + ".svg", "w").write(svg)
        print(base + ".svg")
        if a.png:
            try:
                import cairosvg
                cairosvg.svg2png(bytestring=svg.encode(), write_to=base + ".png", scale=2)
                print(base + ".png")
            except ImportError:
                print("PNG skipped: pip install cairosvg (or open the HTML and screenshot).", file=sys.stderr)
    open(a.out + ".html", "w").write(page(svgs, f'{d["ticker"]} {d.get("fiscal_label","")}'))
    print(a.out + ".html")
