"""Every card renders at every aspect ratio, at the right pixel size, in every style."""
import json, re, unittest
from helpers import TICKERS, load, opt, texts
import render as R

SIZES = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "16:9": (1920, 1080)}


def size(svg):
    m = re.search(r'<svg[^>]*width="(\d+)" height="(\d+)"', svg)
    return int(m.group(1)), int(m.group(2))


class Ratios(unittest.TestCase):
    def test_sizes(self):
        self.assertEqual(R.RATIOS, SIZES)
        for t in TICKERS + ["NVDA-annual", "JPM", "JPM-annual"]:
            d = load(f"{t}.json")
            g = opt(f"{t}-guide-en.json")
            for ratio, wh in SIZES.items():
                with self.subTest(ticker=t, ratio=ratio):
                    cards = dict(R.render_cards(d, "en", "light", None, ratio, "Headline", g))
                    self.assertIn("cover", cards)
                    for name, svg in cards.items():
                        self.assertTrue(texts(svg), name)
                        self.assertEqual(size(svg), (1600, 900) if name == "wide" else wh, name)
                    self.assertEqual("wide" in cards, ratio != "16:9")   # 16:9 cover already is landscape

    def test_landscape_cover_is_the_wide_layout_scaled(self):
        d = load("NVDA.json")
        wide = R.card_wide(d, R.L["en"], "en", R.THEMES["light"], "x")
        cover = R.card_cover(d, R.L["en"], "en", R.THEMES["light"], "x", size=(1920, 1080))
        self.assertIn('viewBox="0 0 1600 900"', cover[:200])
        self.assertEqual(texts(cover), texts(wide))

    def test_styles_and_langs(self):
        d, g = load("META.json"), load("META-guide-zh.json")
        for st in ("dark", "mono", "terminal", "salmon", "pop"):
            for ratio in ("1:1", "9:16", "16:9"):
                with self.subTest(style=st, ratio=ratio):
                    t = R.resolve_style(st)
                    cards = R.render_cards(d, "zh", t, None, ratio, "营收增长 28%", g, load("META-labels.json"))
                    self.assertTrue(all(t["bg"] in svg for _, svg in cards))
        R.apply_style(R.THEMES["light"])


class Web(unittest.TestCase):
    def test_web_render_matches_render_cards(self):
        """The browser calls web_render() with JSON; it must give the same SVGs as the CLI path."""
        d = load("NVDA.json")
        opts = {"lang": "en", "style": "light", "ratio": "4:5", "headline": "Golden test headline",
                "cards": ["cover", "profit"]}
        out = json.loads(R.web_render(json.dumps(d), json.dumps(opts)))
        want = R.render_cards(d, "en", "light", ["cover", "profit"], "4:5", "Golden test headline")
        self.assertEqual([(o["name"], o["svg"]) for o in out], want)
        self.assertEqual((out[0]["w"], out[0]["h"]), (1080, 1350))

    def test_web_render_custom(self):
        d = load("NVDA.json")
        opts = {"style": "light", "font": "serif", "bg": "#0F1A2B", "ink": "#F5F1E8", "hi": "#E8B04B",
                "handle": "@me", "avatar": "data:image/png;base64,AAAA", "ratio": "1:1", "cards": ["cover"]}
        svg = json.loads(R.web_render(json.dumps(d), json.dumps(opts)))[0]["svg"]
        for s in ("#0F1A2B", "#F5F1E8", "#E8B04B", "@me", "<image", "Source Serif 4", 'width="1080" height="1080"'):
            self.assertIn(s, svg)
        R.apply_style(R.THEMES["light"])

    def test_measurer_is_pluggable(self):
        calls = []
        R.set_measurer(lambda s, fam, size, w: calls.append((s, fam)) or len(s) * size * 0.5)
        try:
            self.assertEqual(R.measure("abcd", 10), 20)
            self.assertTrue(calls and "Inter" in calls[0][1])
            R.card_cover(load("NVDA.json"), R.L["zh"], "zh", R.THEMES["light"], "营收翻倍")
            self.assertTrue(any("Noto Sans SC" in f for _, f in calls))
        finally:
            R.set_measurer(None)


if __name__ == "__main__":
    unittest.main()
