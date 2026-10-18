#!/usr/bin/env python3
"""Render a set of earnings cards (SVG + HTML, optional PNG) from fetch_sec.py JSON.

Usage:
  python3 render.py data.json --out ./NVDA [--lang zh|en] [--headline "一句话结论"]
                    [--theme light|dark] [--cards cover,mix,profit,trend,cash,guide,wide]
                    [--guidance guidance.json] [--labels labels.json] [--png]

Cards (1080x1350 unless noted):
  cover   headline, revenue, 8-quarter revenue bars, 4 key metrics
  mix     revenue by business and by region (skipped when the filing has no breakdown)
  profit  waterfall: how every dollar of revenue becomes net income
  trend   8-quarter gross / operating / net margin lines + net income bars
  cash    operating cash flow, capex, free cash flow, buybacks, dividends, cash pile
  guide   next-quarter outlook and last outlook vs actual (only with --guidance)
  wide    1600x900 landscape cover for X / slides
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
    "light": dict(label="Paper · 杂志米白", bg="#F4F1EA", ink="#151515", sub="#6F6A60", faint="#DDD7CB", bar="#CFC8BA",
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
                up="#11A35B", down="#FF2442", card="#FFFFFF", a1="#FF2442", a2="#FF8A00", a3="#7A6E6C", hi="#FF2442",
                round=1.6, stroke=0, band="#FFC9C1",
                palette=["#FF2442", "#FF8A00", "#FFC300", "#3D7BFF", "#11A35B", "#B25CFF", "#7A6E6C", "#FFDCD6"]),
}
THEMES["paper"], THEMES["ink"] = THEMES["light"], THEMES["dark"]   # friendlier aliases
FONT, CJK_FONT, _STYLE = SANS, SANS_SC, {}


def resolve_style(name_or_path):
    """A built-in style name, or a JSON file: {"base": "light", "bg": "#...", "handle": "@me", "avatar": "me.png", ...}."""
    if name_or_path in THEMES:
        return dict(THEMES[name_or_path])
    with open(name_or_path, encoding="utf-8") as f:
        custom = json.load(f)
    t = dict(THEMES[custom.pop("base", "light")])
    fonts = {"sans": (SANS, SANS_SC, PIL_SANS, PIL_SANS_SC), "serif": (SERIF, SERIF_SC, PIL_SERIF, PIL_SERIF_SC),
             "mono": (MONO, SANS_SC, PIL_MONO, PIL_SANS_SC)}
    if custom.get("font") in fonts:
        t["font"], t["cjk_font"], t["pil"], t["pil_cjk"] = fonts[custom.pop("font")]
    av = custom.get("avatar")
    if av and not av.startswith("data:"):
        import base64, mimetypes
        path = av if os.path.isabs(av) else os.path.join(os.path.dirname(os.path.abspath(name_or_path)), av)
        mime = mimetypes.guess_type(path)[0] or "image/png"
        custom["avatar"] = f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()
    t.update(custom)
    return t


def apply_style(t):
    global FONT, CJK_FONT, _STYLE
    if t is not _STYLE:
        FONT, CJK_FONT = t.get("font", SANS), t.get("cjk_font", SANS_SC)
        _STYLE = t
        _FONTS.clear()


L = {
    "zh": dict(rev="营收", gm="毛利率", om="营业利润率", nm="净利率", ni="净利润", eps="稀释每股收益", yoy="同比",
               ended="截至", pts="个百分点", trend="近 8 个季度营收（亿美元）",
               note="数据来源 SEC EDGAR · 不构成投资建议", filed="披露",
               profit_t="营收是怎么变成利润的", cost="营业成本", gp="毛利", rnd="研发", sga="销售及管理",
               other_opex="其他经营费用", oi="营业利润", tax="所得税", other="其他收支", of_rev="占营收",
               trend_t="8 个季度，利润率怎么走", mix_t="钱从哪里来", guide_t="管理层怎么看下季度", next_g="下季指引", kept="上季指引兑现了吗",
               vs_now="较本季", beat="超出指引上限", inline="落在指引区间内", miss="低于指引下限", actual="实际",
               g_src="指引来自公司财报新闻稿（8-K）", by_product="按业务", by_segment="按分部", by_geo="按地区",
               share="占比", other_seg="其他", margins="利润率", ni_bars="净利润（亿美元）",
               cash_t="赚到的钱去了哪", ocf="经营现金流", capex="资本开支", fcf="自由现金流",
               buyback="回购", div="分红", returned="回馈股东", cashpile="现金及短期投资", cashonly="现金及等价物", capex_ocf="资本开支 / 经营现金流", fcf_bars="自由现金流（亿美元）",
               fcf_note="自由现金流 = 经营现金流 − 资本开支"),
    "en": dict(rev="Revenue", gm="Gross margin", om="Operating margin", nm="Net margin", ni="Net income", eps="Diluted EPS",
               yoy="YoY", ended="Quarter ended", pts="pts", trend="Revenue, last 8 quarters ($B)",
               note="Data: SEC EDGAR · Not investment advice", filed="filed",
               profit_t="From revenue to profit", cost="Cost of revenue", gp="Gross profit", rnd="R&D", sga="SG&A",
               other_opex="Other operating costs", oi="Operating income", tax="Income tax", other="Other income", of_rev="of revenue",
               trend_t="8 quarters of margins", mix_t="Where the money comes from", guide_t="What management expects next", next_g="Next-quarter outlook",
               kept="Did they hit last quarter's outlook?", vs_now="vs this qtr", beat="Above the range", inline="Within the range",
               miss="Below the range", actual="Actual", g_src="Outlook from the company's earnings release (8-K)", by_product="By business",
               by_segment="By segment", by_geo="By region", share="share", other_seg="Other", margins="Margins", ni_bars="Net income ($B)",
               cash_t="Where the cash went", ocf="Operating cash flow", capex="Capex", fcf="Free cash flow",
               buyback="Buybacks", div="Dividends", returned="Returned to shareholders", cashpile="Cash & short-term investments", cashonly="Cash & equivalents", capex_ocf="Capex / operating cash flow",
               fcf_bars="Free cash flow ($B)", fcf_note="Free cash flow = operating cash flow − capex"),
}


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
    key = (cjk, bold, size)
    if key not in _FONTS:
        f = None
        try:
            from PIL import ImageFont
            src = _STYLE.get("pil_cjk", PIL_SANS_SC) if cjk else _STYLE.get("pil", PIL_SANS)
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


def measure(s, size, weight=400, ls=0):
    w = 0
    for r, c in _runs(str(s)):
        f = _pil_font(c, weight >= 600, size)
        w += f.getlength(r) if f else sum(size if ord(ch) > 0x2E80 else size * 0.6 for ch in r)
        w += ls * len(r)
    return w


def text(x, y, s, size, fill, weight=400, anchor="start", ls=0):
    # Anchors are resolved here: some SVG rasterizers misplace multi-tspan text with text-anchor.
    if anchor != "start":
        wd = measure(s, size, weight, ls)
        x = round(x - wd if anchor == "end" else x - wd / 2, 1)
    body = "".join(f'<tspan font-family="{CJK_FONT if c else FONT}">{esc(r)}</tspan>' for r, c in _runs(str(s)))
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" letter-spacing="{ls}" xml:space="preserve">{body}</text>')


def wrap(s, max_w, size, weight):
    lines, cur = [], ""
    # break on spaces for Latin text, anywhere for CJK
    for ch in re.findall(r"[A-Za-z0-9$%.,;:()'\-–+~]+ ?|.", s):
        if measure(cur + ch, size, weight) > max_w and cur:
            lines.append(cur)
            cur = ""
        cur += ch
    if cur:
        lines.append(cur)
    return lines[:2]


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
    return f"{v*100:+.1f}%".replace("-", "−") if sign else f"{v*100:.1f}%"


def qlabel(end):
    return f"{end[2:4]}.{int(end[5:7]):02d}"


def yoy_of(trend, key, d):
    """YoY using the trend list (4 quarters back)."""
    if len(trend) < 5:
        return None
    cur, prev = trend[-1].get(key), trend[-5].get(key)
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

    def add(self, *parts):
        self.o.extend(parts)

    def rect(self, x, y, w, h, fill, rx=0, extra=""):
        rx = min(rx * self.t.get("round", 1), max(h, 0) / 2, max(w, 0) / 2) if rx else 0
        self.o.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" height="{max(h,0):.1f}" rx="{rx:g}" fill="{fill}" {extra}/>')

    def box(self, x, y, w, h, rx=18):
        t = self.t
        sw = t.get("stroke", 1.5)
        extra = f'stroke="{t.get("card_stroke", t["faint"])}" stroke-width="{sw}"' if sw else ""
        self.rect(x, y, w, h, t["card"], rx, extra)

    def svg(self):
        return "\n".join(self.o + ["</svg>"])


def company_name(d):
    n = d["company"]
    return n.title() if n.isupper() else n


def footer(c, d, l, lang, P, page=None):
    t = c.t
    fy = c.h - 56
    c.rect(P, fy - 38, c.w - 2 * P, 1.5, t["faint"])
    filing = f'{d["form"].replace(" (derived)", "")} · {d["filed"]} {l["filed"]}'
    c.add(text(P, fy, f'{l["note"]} · {filing}', 18, t["sub"]))
    handle = t.get("handle")
    right = (f"{handle} · " if handle else "") + "earnings-card" + (f"  {CURRENT_PAGE}" if page and CURRENT_PAGE else "")
    c.add(text(c.w - P, fy, right, 18, t["ink"], 700, "end"))
    if t.get("avatar"):
        ax = c.w - P - measure(right, 18, 700) - 22
        cid = f"av{id(c)}"
        c.add(f'<clipPath id="{cid}"><circle cx="{ax:.1f}" cy="{fy-6}" r="14"/></clipPath>'
              f'<image href="{t["avatar"]}" x="{ax-14:.1f}" y="{fy-20}" width="28" height="28" '
              f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{cid})"/>')


def small_header(c, d, l, title, subtitle, P):
    t = c.t
    c.add(text(P, 112, d["ticker"], 34, t["ink"], 800, ls=-0.5))
    c.add(text(P + measure(d["ticker"], 34, 800, -0.5) + 16, 112, company_name(d), 22, t["sub"], 500))
    c.add(text(c.w - P, 112, f'{d.get("fiscal_label","")} · {l["ended"]} {d["period_end"]}', 20, t["sub"], 500, "end"))
    c.rect(P, 140, c.w - 2 * P, 2, t["ink"])
    c.add(text(P, 224, title, 54, t["ink"], 800, ls=-1))
    if subtitle:
        c.add(text(P, 278, subtitle, 26, t["sub"], 500))
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
def card_cover(d, l, lang, t, headline):
    W, H, P = 1080, 1350, 80
    c = Card(W, H, t)
    c.add(text(P, 150, d["ticker"], 92, t["ink"], 800, ls=-2))
    c.add(text(P, 196, company_name(d), 24, t["sub"], 500))
    c.add(text(W - P, 118, d.get("fiscal_label", ""), 30, t["ink"], 700, "end"))
    c.add(text(W - P, 156, f'{l["ended"]} {d["period_end"]}', 22, t["sub"], 400, "end"))
    y = 236
    c.rect(P, y, W - 2 * P, 2, t["ink"])
    y += 70
    if headline:
        lines = wrap(headline, W - 2 * P, 44, 700)
        for i, line in enumerate(lines):
            c.add(text(P, y + i * 58, line, 44, t["ink"], 700))
        y += 58 * len(lines) + 20
    else:
        y -= 10
    c.add(text(P, y + 10, l["rev"], 26, t["sub"], 500))
    up = (d["revenue_yoy"] or 0) >= 0
    c.add(text(P - 4, y + 120, money(d["revenue"], lang), 112, t["ink"], 800, ls=-3))
    pill = f'{pct(d["revenue_yoy"])} {l["yoy"]}'
    pw = measure(pill, 26, 700) + 56
    c.rect(W - P - pw, y + 62, pw, 56, t["up"] if up else t["down"], 28)
    c.add(text(W - P - pw / 2, y + 99, pill, 26, t["bg"], 700, "middle"))
    y += 180
    c.add(text(P, y, l["trend"], 22, t["sub"], 500))
    y += 24
    bars(c, P, y, W - 2 * P, 230 if headline else 290, [q["revenue"] for q in d["trend"]],
         [qlabel(q["end"]) for q in d["trend"]], lang)
    y += (230 if headline else 290) + 74
    cw, chh, g = (W - 2 * P - 24) / 2, 168, 24
    for i, (lab, val, delta) in enumerate(metric_cells(d, l, lang)):
        draw_cell(c, P + (i % 2) * (cw + g), y + (i // 2) * (chh + g), cw, chh, lab, val, delta)
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def card_profit(d, l, lang, t):
    W, H, P = 1080, 1350, 80
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

    label_w = max(measure(r[0], 26, 700) for r in rows) + 36
    val_w = 210
    bx0, bw_max = P + label_w, W - 2 * P - label_w - val_w
    scale = bw_max / max(rev, 1)
    avail = H - 140 - y
    rh = min(92, avail / max(len(rows), 1))
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
        c.add(text(P, ry + rh * 0.5 + 9, lab, 26 if total else 23, t["ink"] if total else t["sub"], 700 if total else 500))
        c.rect(x0, ry + rh * 0.18, max(x1 - x0, 3), rh * 0.64, col, 8)
        vs = money(v, lang) if total else ("−" if v < 0 else "+") + money(abs(v), lang)
        c.add(text(W - P, ry + rh * 0.5 + 2, vs, 28 if total else 24, t["ink"], 800 if total else 600, "end"))
        c.add(text(W - P, ry + rh * 0.5 + 28, f'{abs(v)/rev*100:.1f}% {l["of_rev"]}', 17, t["sub"], 500, "end"))
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
    px = lambda i: x + i * (w - right_pad) / (n - 1)
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


def card_trend(d, l, lang, t):
    W, H, P = 1080, 1350, 80
    c = Card(W, H, t)
    tr = d["trend"]
    g0, g1 = tr[0].get("gross_margin"), tr[-1].get("gross_margin")
    n0, n1 = tr[0].get("net_margin"), tr[-1].get("net_margin")
    if n0 is not None and n1 is not None:
        sub = (f"净利率 {len(tr)} 个季度从 {n0*100:.1f}% 到 {n1*100:.1f}%" if lang == "zh"
               else f"Net margin went from {n0*100:.1f}% to {n1*100:.1f}% in {len(tr)} quarters")
    else:
        sub = ""
    y = small_header(c, d, l, l["trend_t"], sub, P)
    c.add(text(P, y + 10, l["margins"], 22, t["sub"], 500))
    series = [(l["gm"], [q.get("gross_margin") for q in tr], t["a1"]),
              (l["om"], [q.get("operating_margin") for q in tr], t["a2"]),
              (l["nm"], [q.get("net_margin") for q in tr], t["a3"])]
    labels = [qlabel(q["end"]) for q in tr]
    line_chart(c, P + 50, y + 50, W - 2 * P - 50, 420, series, labels, lang)
    y += 560
    c.add(text(P, y, l["ni_bars"], 22, t["sub"], 500))
    bars(c, P, y + 24, W - 2 * P, 250, [q.get("net_income") for q in tr], labels, lang)
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


def card_cash(d, l, lang, t):
    W, H, P = 1080, 1350, 80
    c = Card(W, H, t)
    fcf = d.get("fcf")
    ret = (d.get("buyback") or 0) + (d.get("dividends") or 0)
    if fcf and ret:
        sub = (f"本季回购加分红 {money(ret, lang)}，相当于自由现金流的 {ret/fcf*100:.0f}%" if lang == "zh" and fcf > 0
               else f"本季回购加分红 {money(ret, lang)}" if lang == "zh"
               else f"{money(ret, lang)} returned to shareholders, {ret/fcf*100:.0f}% of free cash flow" if fcf > 0
               else f"{money(ret, lang)} returned to shareholders")
    else:
        sub = l["fcf_note"]
    y = small_header(c, d, l, l["cash_t"], sub, P)

    # Big FCF
    c.add(text(P, y + 10, l["fcf"], 26, t["sub"], 500))
    c.add(text(P - 4, y + 112, money(fcf, lang), 100, t["ink"] if (fcf or 0) >= 0 else t["down"], 800, ls=-3))
    fy = yoy_of(d["trend"], "fcf", d)
    if fy is not None and (d["trend"][-5].get("fcf") or 0) > 0 and (fcf or 0) > 0:
        pill = f'{pct(fy)} {l["yoy"]}'
        pw = measure(pill, 26, 700) + 56
        c.rect(W - P - pw, y + 56, pw, 56, t["up"] if fy >= 0 else t["down"], 28)
        c.add(text(W - P - pw / 2, y + 93, pill, 26, t["bg"], 700, "middle"))
    y += 160

    # Cells
    cells = [(l["ocf"], money(d.get("ocf"), lang), None),
             (l["capex"], money(d.get("capex"), lang),
              (f'{d["capex"]/d["revenue"]*100:.1f}% {l["of_rev"]}', None) if d.get("capex") else None),
             ((l["returned"], money(ret, lang),
               (f'{l["buyback"]} {money(d.get("buyback"), lang)} · {l["div"]} {money(d.get("dividends"), lang)}', None))
              if ret else (l["capex_ocf"], f'{d["capex"]/d["ocf"]*100:.0f}%' if d.get("capex") and d.get("ocf") else "—", None)),
             (l["cashpile"] if d.get("securities") else l["cashonly"], money((d.get("cash") or 0) + (d.get("securities") or 0), lang) if d.get("cash") else "—", None)]
    cw, chh, g = (W - 2 * P - 24) / 2, 164, 24
    for i, (lab, val, delta) in enumerate(cells):
        draw_cell(c, P + (i % 2) * (cw + g), y + (i // 2) * (chh + g), cw, chh, lab, val, delta, vsize=46)
    y += 2 * chh + g + 60
    c.add(text(P, y, l["fcf_bars"], 22, t["sub"], 500))
    bars(c, P, y + 24, W - 2 * P, H - y - 210, [q.get("fcf") for q in d["trend"]],
         [qlabel(q["end"]) for q in d["trend"]], lang)
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
    c.add(text(rx, 252, l["trend"], 20, t["sub"], 500))
    bars(c, rx, 272, rw, my + 2 * chh + g - 272 - 46, [q["revenue"] for q in d["trend"]],
         [qlabel(q["end"]) for q in d["trend"]], lang)
    footer(c, d, l, lang, P)
    return c.svg()


PALETTE = {"light": ["#151515", "#8C6A3F", "#B9A27E", "#6F6A60", "#CFC8BA", "#E3DDD1", "#A8A296", "#EFEAE0"],
           "dark": ["#F2EFE8", "#D9A65E", "#9C7C4E", "#9A958B", "#5A5650", "#3A3733", "#77736B", "#2E2C29"]}


def card_mix(d, l, lang, t, labels=None):
    W, H, P = 1080, 1350, 80
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
    avail = H - 130 - y
    max_rows = [min(len(g[1]), 6 if len(groups) == 1 else 5) for g in groups]
    per_group_fixed = 120
    rh = min(76, (avail - per_group_fixed * len(groups)) / max(sum(max_rows), 1))
    for gi, (title, items) in enumerate(groups):
        items = list(items)
        if len(items) > max_rows[gi]:
            keep = items[:max_rows[gi] - 1]
            rest = items[max_rows[gi] - 1:]
            items = keep + [{"label": l["other_seg"], "value": sum(i["value"] for i in rest),
                             "share": sum(i.get("share") or 0 for i in rest), "yoy": None}]
        c.add(text(P, y + 6, title, 24, t["ink"], 700))
        # 100% stacked bar
        x = P
        bw = W - 2 * P
        by = y + 26
        for k, it in enumerate(items):
            w = bw * (it.get("share") or 0)
            c.rect(x, by, max(w - 3, 1), 30, pal[k % len(pal)], 4)
            x += w
        y = by + 30 + 34
        for k, it in enumerate(items):
            ry = y + k * rh
            c.rect(P, ry - 14, 14, 14, pal[k % len(pal)], 3)
            name = labels.get(it["label"], it["label"])
            if measure(name, 24, 500) > 470:
                while measure(name + "…", 24, 500) > 470 and len(name) > 4:
                    name = name[:-1]
                name += "…"
            c.add(text(P + 28, ry, name, 24, t["ink"], 500))
            c.add(text(P + 640, ry, money(it["value"], lang), 26, t["ink"], 800, "end"))
            c.add(text(P + 760, ry, f'{(it.get("share") or 0)*100:.0f}%', 22, t["sub"], 500, "end"))
            yy = it.get("yoy")
            if yy is not None:
                c.add(text(W - P, ry, f'{pct(yy)} {l["yoy"]}', 22, t["up"] if yy >= 0 else t["down"], 700, "end"))
            c.rect(P, ry + rh * 0.42, W - 2 * P, 1, t["faint"])
        y += len(items) * rh + 40
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


def card_guide(d, l, lang, t, g):
    W, H, P = 1080, 1350, 80
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

    # next quarter outlook
    c.add(text(P, y + 6, f'{l["next_g"]} · {g["next"].get("period", "")}', 24, t["ink"], 700))
    y += 40
    rh = 108
    for k, it in enumerate(nxt[:4]):
        ry = y + k * (rh + 16)
        c.box(P, ry, W - 2 * P, rh, 16)
        c.add(text(P + 28, ry + 42, it["metric"], 22, t["sub"], 500))
        c.add(text(P + 28, ry + 88, _grange(it, lang), 38, t["ink"], 800, ls=-0.5))
        if it.get("base") is not None:
            ds, dv = _gdelta(it, it["base"], lang, l)
            if ds:
                col = t["sub"] if it.get("lower_is_better") else (t["up"] if dv >= 0 else t["down"])
                c.add(text(W - P - 28, ry + 52, ds, 30, col, 800, "end"))
                c.add(text(W - P - 28, ry + 86, f'{l["vs_now"]} {_gfmt(it["base"], it, lang)}', 20, t["sub"], 500, "end"))
    y += len(nxt[:4]) * (rh + 16) + 40

    # did they deliver last quarter's outlook
    pri = (g.get("prior") or {}).get("items") or []
    pri = [p for p in pri if p.get("actual") is not None][:3]
    if pri:
        c.add(text(P, y + 6, f'{l["kept"]} · {g["prior"].get("period", "")}', 24, t["ink"], 700))
        y += 50
        for it in pri:
            lo, hi, act = it["low"], it["high"], it["actual"]
            span = max(hi, act) - min(lo, act)
            pad = span * 0.35 if span else abs(act) * 0.05
            vmin, vmax = min(lo, act) - pad, max(hi, act) + pad
            sx = lambda v: P + 260 + (W - 2 * P - 260 - 40) * (v - vmin) / (vmax - vmin)
            c.add(text(P, y + 34, it["metric"], 24, t["ink"], 600))
            state = "beat" if act > hi + 1e-12 else ("miss" if act < lo - 1e-12 else "inline")
            if it.get("lower_is_better"):
                good = state != "beat"
            else:
                good = state != "miss"
            col = t["sub"] if state == "inline" else (t["up"] if good else t["down"])
            c.add(text(P, y + 66, l[state], 20, col, 700))
            # range band + actual marker
            bx0, bx1 = sx(lo), sx(hi)
            c.rect(P + 260, y + 30, W - 2 * P - 300, 4, t["faint"], 2)
            band = t.get("band", t["bar"])
            c.rect(bx0, y + 18, max(bx1 - bx0, 6), 28, band, 6)
            ax = sx(act)
            c.add(f'<circle cx="{ax:.1f}" cy="{y+32}" r="11" fill="{t["ink"]}"/>')
            c.add(text(ax, y + 2, f'{l["actual"]} {_gfmt(act, it, lang)}', 20, t["ink"], 800, "middle"))
            c.add(text(bx0, y + 72, _gfmt(lo, it, lang), 18, t["sub"], 500, "middle"))
            if bx1 - bx0 > 90:
                c.add(text(bx1, y + 72, _gfmt(hi, it, lang), 18, t["sub"], 500, "middle"))
            y += 118
    note = g.get("note")
    foot = l["g_src"] + (f" · {note}" if note else "")
    for i, line in enumerate(wrap(foot, W - 2 * P, 19, 500)):
        c.add(text(P, H - 160 + i * 26, line, 19, t["sub"], 500))
    footer(c, d, l, lang, P, "__PAGE__")
    return c.svg()


CARDS = {"cover": card_cover, "mix": card_mix, "guide": card_guide, "profit": card_profit, "trend": card_trend, "cash": card_cash, "wide": card_wide}


def page(svgs, title):
    imgs = "\n".join(svgs)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{esc(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;padding:40px 0;display:flex;flex-direction:column;align-items:center;gap:32px;background:#e9e6df}}
svg{{width:min(92vw,540px);height:auto;box-shadow:0 1px 3px rgba(0,0,0,.1)}}svg[width="1600"]{{width:min(92vw,800px)}}</style></head>
<body>{imgs}</body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", required=True, help="output prefix, e.g. ./NVDA")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"])
    ap.add_argument("--headline", default="")
    ap.add_argument("--theme", "--style", dest="theme", default="light",
                    help="built-in style (light/paper, dark/ink, mono, terminal, salmon, pop) or a custom style JSON file")
    ap.add_argument("--cards", default="cover,mix,profit,trend,cash,guide,wide")
    ap.add_argument("--guidance", default="", help="guidance.json written by the agent from fetch_guidance.py output")
    ap.add_argument("--labels", default="", help="JSON file mapping segment labels to display names (e.g. Chinese)")
    ap.add_argument("--png", action="store_true")
    a = ap.parse_args()
    d = json.load(open(a.data))
    t, l = resolve_style(a.theme), L[a.lang]
    labels = json.load(open(a.labels)) if a.labels else {}
    names = [n for n in a.cards.split(",") if n]
    if not (d.get("segments") or {}) and "mix" in names:
        names.remove("mix")
    guidance = json.load(open(a.guidance)) if a.guidance else None
    if not (guidance and (guidance.get("next") or {}).get("items")) and "guide" in names:
        names.remove("guide")
    portrait = [n for n in names if n != "wide"]
    svgs = []
    for i, name in enumerate(names):
        fn = CARDS[name]
        CURRENT_PAGE = f"{portrait.index(name) + 1}/{len(portrait)}" if name in portrait and len(portrait) > 1 else ""
        if name in ("cover", "wide"):
            svg = fn(d, l, a.lang, t, a.headline)
        elif name == "mix":
            svg = fn(d, l, a.lang, t, labels)
        elif name == "guide":
            svg = fn(d, l, a.lang, t, guidance)
        else:
            svg = fn(d, l, a.lang, t)
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
