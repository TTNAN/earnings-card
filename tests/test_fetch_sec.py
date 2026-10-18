import unittest
from helpers import TICKERS, load
from fetch_sec import quarterly, yoy


def fact(start, end, val, filed="2026-01-01", form="10-Q"):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form, "accn": "x"}


class Quarterly(unittest.TestCase):
    def test_derives_q4_from_full_year(self):
        facts = {"Revenues": {"units": {"USD": [
            fact("2025-01-01", "2025-03-31", 10), fact("2025-04-01", "2025-06-30", 20),
            fact("2025-07-01", "2025-09-30", 30),
            fact("2025-01-01", "2025-09-30", 60),
            fact("2025-01-01", "2025-12-31", 100, form="10-K")]}}}
        q = quarterly(facts, ["Revenues"])
        self.assertEqual(q["2025-12-31"][0], 40)
        self.assertIn("derived", q["2025-12-31"][3])

    def test_year_to_date_cash_flow_becomes_quarters(self):
        facts = {"Cash": {"units": {"USD": [
            fact("2025-01-01", "2025-03-31", 5), fact("2025-01-01", "2025-06-30", 12),
            fact("2025-01-01", "2025-09-30", 20)]}}}
        q = quarterly(facts, ["Cash"])
        self.assertEqual([q[e][0] for e in ("2025-03-31", "2025-06-30", "2025-09-30")], [5, 7, 8])

    def test_latest_filing_wins_on_restatement(self):
        facts = {"Revenues": {"units": {"USD": [
            fact("2025-01-01", "2025-03-31", 10, filed="2025-05-01"),
            fact("2025-01-01", "2025-03-31", 11, filed="2026-05-01")]}}}
        self.assertEqual(quarterly(facts, ["Revenues"])["2025-03-31"][0], 11)

    def test_yoy(self):
        s = {"2025-06-30": (150, None), "2024-06-29": (100, None)}
        self.assertAlmostEqual(yoy(s, "2025-06-30"), 0.5)
        self.assertIsNone(yoy({"2025-06-30": (1, None)}, "2025-06-30"))


class FixtureSanity(unittest.TestCase):
    def test_numbers_are_consistent(self):
        for t in TICKERS:
            d = load(f"{t}.json")
            with self.subTest(ticker=t):
                self.assertGreater(d["revenue"], 0)
                self.assertEqual(len(d["trend"]), 8)
                self.assertEqual(d["trend"][-1]["revenue"], d["revenue"])
                self.assertAlmostEqual(d["operating_margin"], d["operating_income"] / d["revenue"], places=6)
                if d.get("ocf") is not None and d.get("capex") is not None:
                    self.assertAlmostEqual(d["fcf"], d["ocf"] - d["capex"], delta=1)
                for k in ("gross_margin", "operating_margin"):
                    if d.get(k) is not None:
                        self.assertTrue(-1 < d[k] < 1, k)


if __name__ == "__main__":
    unittest.main()
