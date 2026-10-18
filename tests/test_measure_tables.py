"""The web worker measures text from width tables the page builds (docs/py/measure_tables.py)."""
import json, os, sys, unittest
from helpers import ROOT

sys.path.insert(0, os.path.join(ROOT, "docs", "py"))


class MeasureTables(unittest.TestCase):
    def setUp(self):
        import render, measure_tables
        self.R, self.M = render, measure_tables

    def tearDown(self):
        self.R.set_measurer(None)

    def test_docs_render_matches_skill(self):
        a = open(os.path.join(ROOT, "docs", "py", "render.py"), encoding="utf-8").read()
        b = open(os.path.join(ROOT, "skills", "earnings-card", "scripts", "render.py"), encoding="utf-8").read()
        self.assertEqual(a, b, "docs/py/render.py must be a copy of the skill's render.py")

    def test_families_cover_every_style(self):
        fams = set(self.M.families())
        for t in self.R.THEMES.values():
            self.assertIn(t.get("font", self.R.SANS), fams)
            self.assertIn(t.get("cjk_font", self.R.SANS_SC), fams)

    def test_sums_scaled_widths(self):
        fam = self.R.SANS
        self.M.set_tables(json.dumps({f"{fam}|400": {"chars": {"A": 60, " ": 25, "，": 100}, "cjk": 100, "other": 50},
                                      f"{fam}|700": {"chars": {"A": 70}, "cjk": 104, "other": 55}}))
        m = self.M.measure
        self.assertAlmostEqual(m("AA A", fam, 20, 400), (60 * 3 + 25) * 0.2)
        self.assertAlmostEqual(m("中文，", fam, 10, 400), 30)       # CJK via representative width
        self.assertAlmostEqual(m("é", fam, 10, 400), 5)              # unlisted non-CJK -> "other"
        self.assertAlmostEqual(m("A", fam, 10, 800), 7)              # nearest weight
        self.assertAlmostEqual(m("A", fam, 10, 500), 6)              # tie between 400/600 goes lighter
        self.assertAlmostEqual(m("AB", "Unknown", 10, 400), 12)      # unmeasured family: rough estimate
        self.assertGreater(self.R.measure("AA", 20, 400), 0)         # installed as render's measurer


if __name__ == "__main__":
    unittest.main()
