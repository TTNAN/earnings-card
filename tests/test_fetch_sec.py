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


class History(unittest.TestCase):
    def facts(self):
        f = lambda st, en, v, filed, form="10-Q", accn="x": {"start": st, "end": en, "val": v, "filed": filed, "form": form, "accn": accn}
        rows = []
        for y in (2024, 2025):
            rows += [f(f"{y}-01-01", f"{y}-03-31", 10 * (y - 2023), f"{y}-05-01", accn=f"q1-{y}"),
                     f(f"{y}-04-01", f"{y}-06-30", 20 * (y - 2023), f"{y}-08-01", accn=f"q2-{y}"),
                     f(f"{y}-07-01", f"{y}-09-30", 30 * (y - 2023), f"{y}-11-01", accn=f"q3-{y}"),
                     f(f"{y}-01-01", f"{y}-09-30", 60 * (y - 2023), f"{y}-11-01", accn=f"q3-{y}"),
                     f(f"{y}-01-01", f"{y}-12-31", 100 * (y - 2023), f"{y + 1}-02-01", "10-K", f"k-{y}")]
        # the 2025 Q1 10-Q repeats 2024 Q1 as a comparative: the original filing must still win
        rows.append(f("2024-01-01", "2024-03-31", 10, "2025-05-01", accn="q1-2025"))
        return {"Revenues": {"units": {"USD": rows}}}

    def ctx(self, facts):
        import fetch_sec as F
        origins = {}
        s = {k: F.quarterly(facts, v, origins if k == "revenue" else None) for k, v in F.TAGS.items()}
        return {"ticker": "T", "period": "quarter", "yearly": False, "cik": 1, "title": "T", "facts": facts,
                "data": {"facts": {"us-gaap": facts}}, "s": s, "origins": origins}

    def test_record_for_an_earlier_quarter(self):
        import fetch_sec as F
        c = self.ctx(self.facts())
        d = F.record(c, "2024-06-30", with_segments=False)
        self.assertEqual((d["revenue"], d["accn"], d["filed"]), (20, "q2-2024", "2024-08-01"))
        self.assertEqual(d["trend"][-1]["end"], "2024-06-30")
        q1 = F.record(c, "2024-03-31", with_segments=False)
        self.assertEqual((q1["accn"], q1["filed"]), ("q1-2024", "2024-05-01"))   # original, not the comparative
        q4 = F.record(c, "2025-12-31", with_segments=False)
        self.assertEqual(q4["revenue"], 200 - 120)
        self.assertEqual(q4["form"], "10-K (derived)")
        self.assertEqual(q4["prev"]["revenue"], 40)       # same quarter a year earlier
        self.assertEqual(q4["prev_q"]["revenue"], 60)     # the quarter before
        self.assertEqual(F.pick_end(c, period_end="2025-07-02"), "2025-06-30")


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
