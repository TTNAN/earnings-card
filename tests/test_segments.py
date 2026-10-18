import unittest
from helpers import TICKERS, load
from segments import _pick_partition


def m(label, v):
    return {"member": label, "label": label, "value": v, "prev": None}


class PickPartition(unittest.TestCase):
    def test_prefers_most_detailed_exact_split(self):
        # Apple-style: Products subtotal overlaps with iPhone/Mac/iPad/Wearables
        items = [m("Products", 70), m("Services", 30), m("iPhone", 45), m("Mac", 10), m("iPad", 8), m("Wearables", 7)]
        got = [i["label"] for i in _pick_partition(items, 100)]
        self.assertEqual(got, ["iPhone", "Services", "Mac", "iPad", "Wearables"])
        self.assertNotIn("Products", got)

    def test_never_double_counts(self):
        items = [m("A", 60), m("B", 40), m("A1", 35), m("A2", 25)]
        got = _pick_partition(items, 100)
        self.assertAlmostEqual(sum(i["value"] for i in got), 100, delta=0.5)

    def test_drops_member_equal_to_total(self):
        items = [m("Total", 100), m("X", 55), m("Y", 45)]
        self.assertEqual([i["label"] for i in _pick_partition(items, 100)], ["X", "Y"])

    def test_adds_other_when_members_fall_short(self):
        items = [m("X", 50), m("Y", 30)]
        got = _pick_partition(items, 100)
        self.assertIn("Other", [i["label"] for i in got])
        self.assertAlmostEqual(sum(i["value"] for i in got), 100, delta=0.5)

    def test_single_member_is_not_a_breakdown(self):
        self.assertEqual(_pick_partition([m("X", 100)], 100), [])
        self.assertEqual(_pick_partition([m("X", 60)], 100), [])

    def test_ignores_zero_and_negative(self):
        items = [m("X", 70), m("Y", 30), m("Z", 0), m("W", -5)]
        self.assertEqual([i["label"] for i in _pick_partition(items, 100)], ["X", "Y"])


class FixtureSegments(unittest.TestCase):
    """Every saved breakdown must add up to reported revenue."""
    def test_breakdowns_sum_to_revenue(self):
        for t in TICKERS:
            d = load(f"{t}.json")
            for axis, rows in (d.get("segments") or {}).items():
                with self.subTest(ticker=t, axis=axis):
                    total = sum(r["value"] for r in rows)
                    self.assertAlmostEqual(total / d["revenue"], 1, delta=0.01)
                    self.assertAlmostEqual(sum(r["share"] for r in rows), 1, delta=0.01)


if __name__ == "__main__":
    unittest.main()
