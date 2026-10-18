"""Quick entries (just reported, earnings calendar), share metadata, style thumbnails and the
serif display face of the magazine style."""
import json, os, re, sys, unittest
from helpers import ROOT, load
import render as R

sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_data  # noqa: E402
import build_calendar as C  # noqa: E402

DOCS = os.path.join(ROOT, "docs")
DATA = os.path.join(DOCS, "data")
STYLES = [k for k in R.THEMES if k not in ("paper", "ink")]


class CoverageFiled(unittest.TestCase):
    def test_row_has_newest_filing(self):
        d = {"ticker": "X",
             "quarter": {"periods": [{"period_end": "2026-03-31", "filed": "2026-05-01"},
                                     {"period_end": "2026-06-30", "filed": "2026-08-01"}]},
             "annual": {"periods": [{"period_end": "2025-12-31", "filed": "2026-02-20"}]}}
        self.assertEqual(build_data.coverage_row(d, {})["filed"], "2026-08-01")
        self.assertEqual(build_data.coverage_row({"ticker": "Y"}, {})["filed"], "")

    def test_coverage_file_has_filed_dates(self):
        cov = json.load(open(os.path.join(DATA, "coverage.json"), encoding="utf-8"))
        self.assertTrue(all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["filed"]) for r in cov))
        nv = next(r for r in cov if r["t"] == "NVDA")
        rec = json.load(open(os.path.join(DATA, "NVDA.json"), encoding="utf-8"))
        self.assertEqual(nv["filed"], max(rec[p]["periods"][-1]["filed"] for p in ("quarter", "annual")))


class Calendar(unittest.TestCase):
    PAYLOAD = {"data": {"rows": [
        {"symbol": "NFLX", "time": "time-after-hours"},
        {"symbol": "GE", "time": "time-pre-market"},
        {"symbol": "BRK/B", "time": "time-not-supplied"},
        {"symbol": "ZZZZ", "time": "time-pre-market"},
        {"symbol": None},
    ]}}

    def test_parse_filters_and_maps_time(self):
        rows = C.parse_day(self.PAYLOAD, "2026-10-20", {"NFLX", "GE", "BRK.B"})
        self.assertEqual(rows, [{"t": "NFLX", "date": "2026-10-20", "time": "amc"},
                                {"t": "GE", "date": "2026-10-20", "time": "bmo"},
                                {"t": "BRK.B", "date": "2026-10-20", "time": ""}])

    def test_parse_empty_day(self):
        self.assertEqual(C.parse_day({"data": {"rows": None}}, "2026-10-24", {"GE"}), [])
        self.assertEqual(C.parse_day({"data": None}, "2026-10-24", {"GE"}), [])
        self.assertEqual(C.parse_day(None, "2026-10-24", {"GE"}), [])

    def test_merge_keeps_earliest_and_sorts(self):
        rows = [{"t": "B", "date": "2026-10-21", "time": "amc"}, {"t": "A", "date": "2026-10-21", "time": "amc"},
                {"t": "C", "date": "2026-10-21", "time": "bmo"}, {"t": "B", "date": "2026-10-20", "time": ""},
                {"t": "C", "date": "2026-10-28", "time": "bmo"}]
        self.assertEqual([(r["t"], r["date"]) for r in C.merge(rows)],
                         [("B", "2026-10-20"), ("C", "2026-10-21"), ("A", "2026-10-21")])

    def test_calendar_file(self):
        p = os.path.join(DATA, "calendar.json")
        if not os.path.exists(p):
            self.skipTest("no calendar.json")
        cal = json.load(open(p, encoding="utf-8"))
        supported = {t for t, _ in json.load(open(os.path.join(DATA, "tickers.json"), encoding="utf-8"))}
        self.assertRegex(cal["updated"], r"^\d{4}-\d{2}-\d{2}$")
        for r in cal["rows"]:
            self.assertIn(r["t"], supported)
            self.assertRegex(r["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertIn(r["time"], ("bmo", "amc", ""))
        self.assertEqual(len({r["t"] for r in cal["rows"]}), len(cal["rows"]))


class ShareMeta(unittest.TestCase):
    PAGES = ["index.html", "gallery/index.html", "tickers/index.html"]

    def test_absolute_custom_domain(self):
        for pg in self.PAGES:
            html = open(os.path.join(DOCS, pg), encoding="utf-8").read()
            self.assertNotIn("ttnan.github.io", html, pg)
            self.assertIn('<meta property="og:image" content="https://earningscard.tech/og.png">', html, pg)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', html, pg)
            url = re.search(r'<meta property="og:url" content="([^"]+)">', html).group(1)
            self.assertTrue(url.startswith("https://earningscard.tech/"), pg)
            self.assertIn(f'<link rel="canonical" href="{url}">', html, pg)
            self.assertIn('favicon.svg"', html, pg)
            self.assertIn('apple-touch-icon.png"', html, pg)

    def test_images_exist(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        self.assertEqual(Image.open(os.path.join(DOCS, "og.png")).size, (1200, 630))
        self.assertEqual(Image.open(os.path.join(DOCS, "favicon-32.png")).size, (32, 32))
        self.assertEqual(Image.open(os.path.join(DOCS, "apple-touch-icon.png")).size, (180, 180))
        self.assertTrue(open(os.path.join(DOCS, "favicon.svg")).read().startswith("<svg"))

    def test_style_thumbnails(self):
        js = open(os.path.join(DOCS, "app.js"), encoding="utf-8").read()
        ids = re.findall(r'\{id: "(\w+)", zh:', js)
        self.assertEqual(sorted(ids), sorted(STYLES))
        for s in ids:
            self.assertTrue(os.path.getsize(os.path.join(DOCS, "styles", "thumbs", s + ".webp")) > 500, s)
        main = json.loads(re.search(r"const MAIN_STYLES = (\[[^\]]+\])", js).group(1))
        rec = json.loads(re.search(r"const REC_STYLES = (\[[^\]]+\])", js).group(1))
        self.assertLessEqual(len(main), 8)
        self.assertEqual(main[0], "light")
        self.assertEqual(len(rec), 3)
        self.assertTrue(set(rec) <= set(main) <= set(ids))


class DisplayFont(unittest.TestCase):
    def setUp(self):
        self.d = load("NVDA.json")

    def head_family(self, style, lang, card="cover"):
        svg = dict(R.render_cards(self.d, lang, style, [card], "4:5", "营收翻倍" if lang == "zh" else "Revenue doubled"))[card]
        m = re.search(r'<text [^>]*font-family="([^"]+)"[^>]*>(?:<tspan[^>]*>[^<]*</tspan>)*?<tspan font-family="([^"]+)">(营收翻倍|Revenue doubled)', svg)
        return m.group(1), m.group(2)

    def test_magazine_headline_serif(self):
        self.assertEqual(self.head_family(R.build_style({"base": "light"}), "zh")[1], R.SERIF_SC)
        self.assertEqual(self.head_family(R.build_style({"base": "light"}), "en")[1], R.SERIF)

    def test_body_stays_sans(self):
        svg = dict(R.render_cards(self.d, "zh", R.build_style({"base": "light"}), ["cover"], "4:5"))["cover"]
        self.assertIn(f'font-family="{R.SANS}"', svg)

    def test_explicit_font_and_other_styles(self):
        self.assertEqual(self.head_family(R.build_style({"base": "light", "font": "sans"}), "en")[1], R.SANS)
        self.assertEqual(self.head_family(R.build_style({"base": "dark"}), "en")[1], R.SANS)

    def test_display_does_not_leak(self):
        R.render_cards(self.d, "en", R.build_style({"base": "light"}), ["cover", "profit"], "4:5", "Revenue doubled")
        self.assertEqual((R.FONT, R.CJK_FONT, R._PIL_OVR), (R.SANS, R.SANS_SC, None))


if __name__ == "__main__":
    unittest.main()
