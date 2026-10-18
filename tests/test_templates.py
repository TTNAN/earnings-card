"""The five extra templates, the six newer styles, and choosing a period from a multi-period data file."""
import glob, json, os, re, unittest
from helpers import ROOT, load, opt, texts
import render as R

SIZES = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "16:9": (1920, 1080)}
ALL_STYLES = ["light", "dark", "mono", "terminal", "salmon", "pop", "bloomberg", "keynote", "neon", "vintage", "morandi", "glass"]


def size(svg):
    m = re.search(r'<svg[^>]*width="(\d+)" height="(\d+)"', svg)
    return int(m.group(1)), int(m.group(2))


class Templates(unittest.TestCase):
    def test_every_template_style_ratio_lang(self):
        block = load("NVDA-v2.json")["quarter"]
        d = R.period_record(block)
        for st in ALL_STYLES:
            t = R.build_style({"base": st, "handle": "@me"})
            for ratio, wh in SIZES.items():
                for lang in ("zh", "en"):
                    with self.subTest(style=st, ratio=ratio, lang=lang):
                        cards = dict(R.render_cards(d, lang, t, R.EXTRA_CARDS, ratio, "Headline"))
                        self.assertEqual(sorted(cards), sorted(R.EXTRA_CARDS))
                        for name, svg in cards.items():
                            self.assertEqual(size(svg), wh, name)
                            self.assertIn(t["bg"], svg, name)
                            self.assertTrue(texts(svg), name)
        R.apply_style(R.THEMES["light"])

    def test_old_fixtures_without_prev_still_render(self):
        """Records from fetch_sec.py before "prev" existed: year-ago figures come from the trend."""
        for fx in ("AAPL", "JPM", "NVDA-annual", "JPM-annual"):
            d = load(f"{fx}.json")
            with self.subTest(fx=fx):
                names = [n for n, _ in R.render_cards(d, "en", "light", R.EXTRA_CARDS, "4:5")]
                self.assertEqual(names, R.EXTRA_CARDS)

    def test_defaults_unchanged(self):
        self.assertEqual(R.DEFAULT_CARDS, ["cover", "mix", "profit", "trend", "cash", "guide", "wide"])
        names = [n for n, _ in R.render_cards(load("NVDA.json"), "en", "light", None, "4:5", "", load("NVDA-guide-en.json"))]
        self.assertFalse(set(names) & set(R.EXTRA_CARDS))

    def test_poster_is_revenue_and_yoy(self):
        d = R.period_record(load("NVDA-v2.json")["quarter"])
        svg = R.card_poster(d, R.L["en"], "en", R.THEMES["light"], "")
        txt = "".join(texts(svg)).replace(" ", "")   # the figure is drawn in parts (smaller $ and unit)
        self.assertIn(R.money(d["revenue"], "en"), txt)
        self.assertIn(f'{R.pct(d["revenue_yoy"])}YoY', txt)

    def test_post_uses_handle_or_default(self):
        d = R.period_record(load("NVDA-v2.json")["quarter"])
        svg = R.card_post(d, R.L["en"], "en", R.THEMES["light"], "")
        self.assertIn("earnings-card", "".join(texts(svg)))
        t = R.build_style({"base": "dark", "handle": "@caesar", "avatar": "data:image/png;base64,AAAA"})
        svg = R.card_post(d, R.L["en"], "en", t, "")
        self.assertIn("@caesar", "".join(texts(svg)))
        self.assertIn("<image", svg)
        R.apply_style(R.THEMES["light"])

    def test_income_has_year_ago_column(self):
        d = R.period_record(load("NVDA-v2.json")["quarter"])
        txt = texts(R.card_income(d, R.L["en"], "en", R.THEMES["light"]))
        self.assertIn(R.money(d["prev"]["revenue"], "en"), txt)
        self.assertIn(f'${d["eps"]:.2f}', txt)

    def test_scoreboard_says_what_it_compares_and_never_consensus(self):
        b = load("NVDA-v2.json")["quarter"]
        d = R.period_record(b)
        g = load("NVDA-guide-en.json")
        for guide in (None, g):
            for lang in ("en", "zh"):
                with self.subTest(guide=bool(guide), lang=lang):
                    txt = "".join(texts(R.card_score(d, R.L[lang], lang, R.THEMES["light"], guide)))
                    if lang == "en":
                        self.assertIn("not analyst consensus", txt)
                        self.assertIn("prior outlook" if guide else "previous quarter", txt)
                    else:
                        self.assertIn("不是市场一致预期", txt)
                        self.assertIn("指引" if guide else "上一季度", txt)
        a = R.period_record(load("NVDA-v2.json")["annual"])
        txt = "".join(texts(R.card_score(a, R.L["en"], "en", R.THEMES["light"], g)))
        self.assertIn("previous fiscal year", txt)   # outlooks are quarterly: annual cards compare years

    def test_web_render_extra_cards(self):
        b = load("NVDA-v2.json")["quarter"]
        out = json.loads(R.web_render(json.dumps(b), json.dumps({"style": "neon", "cards": R.EXTRA_CARDS, "ratio": "9:16"})))
        self.assertEqual([o["name"] for o in out], R.EXTRA_CARDS)


class Styles12(unittest.TestCase):
    def test_twelve_styles(self):
        self.assertEqual([k for k in R.THEMES if k not in ("paper", "ink")], ALL_STYLES)

    def test_glass_gradient_and_translucent_cards(self):
        d = load("NVDA.json")
        svg = R.card_cover(d, R.L["en"], "en", R.resolve_style("glass"), "x")
        self.assertIn("<linearGradient", svg)
        self.assertIn('fill-opacity="0.42"', svg)
        # two cards on one web page must not share a gradient id
        ids = re.findall(r'linearGradient id="(\w+)"', svg + R.card_profit(d, R.L["en"], "en", R.resolve_style("glass")))
        self.assertEqual(len(ids), len(set(ids)))
        # a custom page colour replaces the gradient
        t = R.recolor(R.resolve_style("glass"), bg="#101010")
        self.assertNotIn("<linearGradient", R.card_cover(d, R.L["en"], "en", t, "x"))
        R.apply_style(R.THEMES["light"])

    def test_no_svg_filters(self):
        """cairosvg and every browser must draw them the same: no filters, blur or masks."""
        d = R.period_record(load("NVDA-v2.json")["quarter"])
        for st in ALL_STYLES:
            for name, svg in R.render_cards(d, "en", st, R.DEFAULT_CARDS + R.EXTRA_CARDS, "4:5", "x"):
                self.assertNotIn("<filter", svg, (st, name))
                self.assertNotIn("<mask", svg, (st, name))
        R.apply_style(R.THEMES["light"])


class Periods(unittest.TestCase):
    def test_default_is_latest(self):
        b = load("NVDA-v2.json")["quarter"]
        d = R.period_record(b)
        self.assertEqual(d["period_end"], b["periods"][-1]["period_end"])
        self.assertEqual(d["trend"][-1]["end"], d["period_end"])
        self.assertEqual(d["trend"][-1]["revenue"], d["revenue"])
        self.assertEqual(len(d["trend"]), 8)

    def test_pick_by_end_and_by_fiscal_label(self):
        b = load("NVDA-v2.json")["quarter"]
        p = b["periods"][2]
        d = R.period_record(b, p["period_end"])
        self.assertEqual(d["fiscal_label"], p["fiscal_label"])
        self.assertEqual(d["trend"][-1]["end"], p["period_end"])      # its own window, ending at that period
        self.assertEqual(len(d["trend"]), 8)
        self.assertEqual(d["trend"][-1]["revenue"], d["revenue"])
        self.assertTrue(all(q["end"] <= p["period_end"] for q in d["trend"]))
        fy, fq = re.match(r"FY(\d{4}) Q(\d)", p["fiscal_label"]).groups()
        self.assertEqual(R.period_record(b, fy=fy, fq=fq)["period_end"], p["period_end"])
        self.assertIsNone(R.period_record(b, "1999-01-01"))
        a = load("NVDA-v2.json")["annual"]
        first = a["periods"][0]
        d = R.period_record(a, fy=first["fiscal_label"][2:])
        self.assertEqual(d["period_end"], first["period_end"])
        self.assertEqual(len(d["trend"]), 5)
        self.assertEqual(d["period"], "annual")

    def test_plain_record_passes_through(self):
        d = load("NVDA.json")
        self.assertIs(R.period_record(d), d)

    def test_web_render_period_end(self):
        b = load("NVDA-v2.json")["quarter"]
        p = b["periods"][0]
        out = json.loads(R.web_render(json.dumps(b), json.dumps({"cards": ["cover"], "period_end": p["period_end"]})))
        self.assertIn(p["fiscal_label"], "".join(texts(out[0]["svg"])))


class DataSchema(unittest.TestCase):
    def test_every_data_file(self):
        files = [f for f in glob.glob(os.path.join(ROOT, "docs", "data", "*.json"))
                 if os.path.basename(f)[:-5].replace("-", "").isupper()]
        self.assertGreater(len(files), 50)
        for f in files:
            rec = json.load(open(f, encoding="utf-8"))
            with self.subTest(file=os.path.basename(f)):
                self.assertEqual(rec.get("v"), 2)
                self.assertTrue(rec.get("quarter") or rec.get("annual"))
                for per, n in (("quarter", 8), ("annual", 5)):
                    b = rec.get(per)
                    if not b:
                        continue
                    self.assertEqual(b["period"], per)
                    ends = [p["period_end"] for p in b["periods"]]
                    self.assertEqual(ends, sorted(ends))
                    self.assertLessEqual(len(ends), n)
                    series_ends = [q["end"] for q in b["series"]]
                    self.assertEqual(series_ends, sorted(set(series_ends)))
                    for p in b["periods"]:
                        self.assertNotIn("trend", p)
                        for k in ("period_end", "fiscal_label", "revenue", "form", "filed", "segments", "prev"):
                            self.assertIn(k, p)
                        d = R.period_record(b, p["period_end"])
                        self.assertEqual(d["trend"][-1]["end"], p["period_end"])
                        self.assertEqual(d["trend"][-1]["revenue"], d["revenue"])


if __name__ == "__main__":
    unittest.main()
