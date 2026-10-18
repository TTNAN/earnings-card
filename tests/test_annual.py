"""Full-year (10-K) mode: fetch_sec.annual() and the cards it feeds."""
import json, unittest
from helpers import load, texts
from fetch_sec import annual
import render as R


def fact(start, end, val, filed="2026-01-01", form="10-K"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form, "accn": "x"}


class Annual(unittest.TestCase):
    def test_keeps_only_full_years(self):
        facts = {"Revenues": {"units": {"USD": [
            fact("2025-01-01", "2025-03-31", 10, form="10-Q"),
            fact("2024-01-01", "2024-12-31", 90), fact("2025-01-01", "2025-12-31", 100)]}}}
        a = annual(facts, ["Revenues"])
        self.assertEqual(sorted(a), ["2024-12-31", "2025-12-31"])
        self.assertEqual(a["2025-12-31"][0], 100)

    def test_latest_10k_wins(self):
        facts = {"Revenues": {"units": {"USD": [
            fact("2025-01-01", "2025-12-31", 100, filed="2026-02-01"),
            fact("2025-01-01", "2025-12-31", 101, filed="2027-02-01"),
            fact("2025-01-01", "2025-12-31", 999, filed="2028-02-01", form="8-K")]}}}
        self.assertEqual(annual(facts, ["Revenues"])["2025-12-31"][0], 101)

    def test_fixture_shape(self):
        for t in ("NVDA", "AAPL"):
            d = load(f"{t}-annual.json")
            with self.subTest(ticker=t):
                self.assertEqual(d["period"], "annual")
                self.assertRegex(d["fiscal_label"], r"^FY\d{4}$")
                self.assertTrue(d["form"].startswith("10-K"))
                self.assertEqual(len(d["trend"]), 5)
                self.assertEqual(d["trend"][-1]["revenue"], d["revenue"])
                self.assertTrue(all(q["label"].startswith("FY") for q in d["trend"]))


class AnnualCards(unittest.TestCase):
    def test_renders_with_year_labels(self):
        d = load("NVDA-annual.json")
        for lang in ("en", "zh"):
            cards = dict(R.render_cards(d, lang, "light", None, "4:5", "x", load("NVDA-guide-en.json")))
            with self.subTest(lang=lang):
                self.assertNotIn("guide", cards)                    # outlook is a quarterly thing
                self.assertEqual(sorted(cards), sorted(["cover", "mix", "profit", "trend", "cash", "wide"]))
                cover = " ".join(texts(cards["cover"]))
                self.assertIn("FY2026", cover)
                self.assertIn("FY26", cover)
                self.assertIn("Fiscal year ended" if lang == "en" else "财年截至", cover)
                self.assertNotIn("quarter", " ".join(texts(cards["trend"])).lower())
                self.assertIn("FY22", texts(cards["wide"]))                  # bar labels, not dates

    def test_annual_yoy_uses_prior_year(self):
        d = load("NVDA-annual.json")
        tr = d["trend"]
        want = (tr[-1]["fcf"] - tr[-2]["fcf"]) / abs(tr[-2]["fcf"])
        self.assertAlmostEqual(R.yoy_of(tr, "fcf", d), want)


if __name__ == "__main__":
    unittest.main()
