"""Web generator UX helpers: share caption, headline ideas, unit formatting, style contrast,
one-card-at-a-time rendering, custom accents, and the coverage index for the ticker list."""
import glob, json, os, re, sys, unittest
from helpers import ROOT, load
import render as R

sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_data  # noqa: E402

DATA = os.path.join(ROOT, "docs", "data")
STYLES = ["light", "dark", "mono", "terminal", "salmon", "pop", "bloomberg", "keynote", "neon", "vintage", "morandi", "glass"]


def block(tk, period="quarter"):
    with open(os.path.join(DATA, f"{tk}.json"), encoding="utf-8") as f:
        return json.load(f).get(period)


def data_files():
    return [f for f in sorted(glob.glob(os.path.join(DATA, "*.json"))) if os.path.basename(f)[:-5].replace("-", "").isupper()]


def visible_text(svg):
    s = re.sub(r"<[^>]+>", " ", svg)
    return " ".join(s.replace("&amp;", "&").split())


class Caption(unittest.TestCase):
    def setUp(self):
        self.d = R.period_record(block("NVDA"))

    def test_zh_caption_has_the_facts_in_yi(self):
        c = R.caption(self.d, "zh", "英伟达")
        self.assertIn("英伟达（NVDA）", c)
        self.assertIn(self.d["fiscal_label"], c)
        self.assertIn(f'营收 {R.money(self.d["revenue"], "zh")}，同比 {R.pct(self.d["revenue_yoy"])}', c)
        self.assertIn(f'毛利率 {R.pct(self.d["gross_margin"], False)}', c)
        self.assertIn(f'${self.d["eps"]:.2f}', c)
        self.assertIn("#NVDA", c)
        self.assertIn("#英伟达", c)
        self.assertIn("不构成投资建议", c)
        self.assertNotRegex(c, r"\d\s?B\b")

    def test_en_caption_uses_billions(self):
        c = R.caption(self.d, "en")
        self.assertIn(f'Revenue {R.money(self.d["revenue"], "en")}', c)
        self.assertRegex(c, r"\$\d[\d,]*\.\dB")
        self.assertNotIn("亿", c)
        self.assertIn("#NVDA #earnings", c)

    def test_partial_data_caption_skips_missing(self):
        d = R.period_record(block("BRK-B"))   # no EPS in the data
        c = R.caption(d, "en")
        self.assertNotIn("EPS", c)
        self.assertIn("#BRKB", c)

    def test_no_yoy_on_a_loss(self):
        d = dict(R.period_record(block("NVDA")))
        d["net_income"], d["prev"] = -5e9, dict(d["prev"], net_income=-1e9)
        self.assertNotIn("净利润 −$50.0亿，同比", R.caption(d, "zh"))


class Headlines(unittest.TestCase):
    def test_ideas_are_short_and_from_the_numbers(self):
        for tk in ("NVDA", "MSFT", "JPM", "INTC", "XOM", "AAPL"):
            for period in ("quarter", "annual"):
                b = block(tk, period)
                if not b:
                    continue
                d = R.period_record(b)
                for lang in ("zh", "en"):
                    ideas = R.headline_ideas(d, lang)
                    self.assertLessEqual(len(ideas), 3)
                    self.assertEqual(len(ideas), len(set(ideas)))
                    cap = R.caption(d, lang)
                    for h in ideas:
                        self.assertLessEqual(len(h), 60, h)
                        # every money figure in a headline is one the caption (i.e. the data) also prints
                        for m in re.findall(r"\$[\d,.]+(?:亿|B|M|万)?", h):
                            self.assertIn(m, cap, (tk, period, lang, h))
                        self.assertNotRegex(h, r"(?i)consensus|预期|beat|超预期")

    def test_doubled_only_when_it_did(self):
        d = dict(R.period_record(block("NVDA")))
        d["revenue_yoy"] = 0.99
        self.assertFalse(any("翻倍" in h for h in R.headline_ideas(d, "zh")))
        d["revenue_yoy"] = 1.06
        self.assertTrue(any("翻倍" in h for h in R.headline_ideas(d, "zh")))

    def test_web_extras(self):
        b = block("NVDA")
        out = json.loads(R.web_extras(json.dumps(b), json.dumps({"lang": "en", "period_end": b["periods"][-2]["period_end"]})))
        self.assertIn(b["periods"][-2]["fiscal_label"], out["caption"])
        self.assertTrue(out["headlines"])


class Units(unittest.TestCase):
    def test_money(self):
        self.assertEqual(R.money(96.221e9, "en"), "$96.2B")
        self.assertEqual(R.money(96.221e9, "zh"), "$962.2亿")
        self.assertEqual(R.money(850e6, "en"), "$850M")
        self.assertEqual(R.money(-11.03e9, "zh"), "−$110.3亿")
        self.assertEqual(R.pct(-0.684, False), "−68.4%")

    def test_cards_never_mix_units(self):
        """zh cards print money in 亿 (never B/M); en cards in B/M (never 亿/万)."""
        for tk in ("NVDA", "AAPL", "JPM", "XOM", "INTC", "KO"):
            for period in ("quarter", "annual"):
                b = block(tk, period)
                if not b:
                    continue
                d = R.period_record(b)
                for lang in ("zh", "en"):
                    for name, svg in R.render_cards(d, lang, "light", list(R.CARDS), "4:5"):
                        txt = visible_text(svg)
                        if lang == "zh":
                            self.assertNotRegex(txt, r"\$[\d.,]+\s?[BM]\b", (tk, period, name))
                        else:
                            self.assertNotRegex(txt, r"[亿万]", (tk, period, name))


class Contrast(unittest.TestCase):
    def test_builtin_styles(self):
        """Body text >= 4.5:1 and coloured figures / highlights >= 3:1 on the page and on the boxes."""
        for s in STYLES:
            t = R.THEMES[s]
            grounds = [t["bg"]] + list(t.get("bg_grad") or [])
            if not t.get("card_opacity"):
                grounds.append(t["card"])
            for g in grounds:
                for k in ("ink", "sub"):
                    self.assertGreaterEqual(R.contrast(t[k], g), 4.5, (s, k, g))
                for k in ("up", "down", "hi", "a2"):
                    if k not in t:   # falls back to ink
                        continue
                    self.assertGreaterEqual(R.contrast(t[k], g), 3.0, (s, k, g))

    def test_custom_colours_keep_secondary_text_readable(self):
        t = R.recolor(R.THEMES["light"], bg="#336699", ink="#FFFFFF")
        self.assertGreaterEqual(R.contrast(t["sub"], t["bg"]), 4.5)
        self.assertEqual(R.ensure_contrast("#000000", "#FFFFFF"), "#000000")

    def test_extra_accent_and_red_up(self):
        base = R.THEMES["light"]
        t = R.recolor(base, a2="#00AA88", updown="cn")
        self.assertEqual(t["a2"], "#00AA88")
        self.assertEqual((t["up"], t["down"]), (base["down"], base["up"]))
        out = json.loads(R.web_render(json.dumps(block("NVDA")), json.dumps({"cards": ["trend"], "a2": "#00AA88"})))
        self.assertIn("#00AA88", out[0]["svg"])


class OneAtATime(unittest.TestCase):
    def test_only_matches_the_full_set(self):
        b, o = block("NVDA"), {"cards": ["cover", "mix", "profit", "trend", "cash", "wide"], "lang": "zh"}
        full = json.loads(R.web_render(json.dumps(b), json.dumps(o)))
        for i, card in enumerate(full):
            one = json.loads(R.web_render(json.dumps(b), json.dumps(dict(o, only=i))))
            self.assertEqual(one["names"], [c["name"] for c in full])
            self.assertEqual(one["cards"][0]["svg"], card["svg"])   # same page number "i/n" in the footer too

    def test_card_names_drops_cards_without_data(self):
        d = R.period_record(block("NVDA", "annual"))
        self.assertNotIn("guide", R.card_names(d, ["cover", "guide", "wide"], "16:9"))
        self.assertNotIn("wide", R.card_names(d, ["cover", "wide"], "16:9"))


class Coverage(unittest.TestCase):
    def test_coverage_file_matches_data(self):
        with open(os.path.join(DATA, "coverage.json"), encoding="utf-8") as f:
            cov = {r["t"]: r for r in json.load(f)}
        with open(os.path.join(DATA, "tickers.json"), encoding="utf-8") as f:
            tickers = [t for t, _ in json.load(f)]
        self.assertEqual(sorted(cov), sorted(tickers))
        self.assertIn("no_quarter", cov["BNY"]["partial"])
        self.assertIn("no_annual", cov["XOM"]["partial"])
        self.assertEqual(cov["NVDA"]["partial"], [])
        self.assertEqual(cov["NVDA"]["zh"], "英伟达")
        for r in cov.values():
            self.assertTrue(r["q"] or r["a"])

    def test_meta_covers_every_ticker(self):
        with open(os.path.join(ROOT, "tools", "ticker_meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(DATA, "tickers.json"), encoding="utf-8") as f:
            for t, _ in json.load(f):
                self.assertIn(t, meta)

    def test_coverage_row(self):
        d = {"ticker": "X", "quarter": {"periods": [{"period_end": "2026-01-01", "fiscal_label": "FY2026 Q1", "revenue": 1}]}}
        r = build_data.coverage_row(d, {})
        self.assertEqual(r["q"], ["FY2026 Q1"])
        self.assertIn("no_annual", r["partial"])
        self.assertIn("few_quarter", r["partial"])
        self.assertTrue(any(p.startswith("quarter:") for p in r["partial"]))


if __name__ == "__main__":
    unittest.main()
