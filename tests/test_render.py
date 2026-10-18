"""Golden tests: every number printed on every card is compared with tests/golden.

After an intentional change, refresh the snapshots with:
    UPDATE_GOLDEN=1 python -m unittest discover tests
"""
import json, os, unittest
from helpers import GOLD, TICKERS, render_all, texts, norm, same
import render as R


class Formatting(unittest.TestCase):
    def test_money(self):
        self.assertEqual(R.money(96_221_000_000, "en"), "$96.2B")
        self.assertEqual(R.money(96_221_000_000, "zh"), "$962.2亿")
        self.assertEqual(R.money(431_000_000, "en"), "$431M")
        self.assertEqual(R.money(-5_850_000_000, "zh"), "−$58.5亿")
        self.assertEqual(R.money(2.5e12, "zh"), "$2.50万亿")
        self.assertEqual(R.money(None, "en"), "—")

    def test_pct(self):
        self.assertEqual(R.pct(0.2416), "+24.2%")
        self.assertEqual(R.pct(-0.136), "−13.6%")
        self.assertEqual(R.pct(0.75, sign=False), "75.0%")


class Golden(unittest.TestCase):
    maxDiff = None

    def test_cards_match_golden(self):
        update = os.environ.get("UPDATE_GOLDEN")
        for t in TICKERS:
            for lang in ("en", "zh"):
                cards = {k: texts(v) for k, v in render_all(t, lang).items()}
                path = os.path.join(GOLD, f"{t}-{lang}.json")
                if update or not os.path.exists(path):
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(cards, f, ensure_ascii=False, indent=1)
                    continue
                with open(path, encoding="utf-8") as f:
                    want = json.load(f)
                with self.subTest(ticker=t, lang=lang):
                    self.assertEqual(sorted(cards), sorted(want), "set of cards changed")
                    for k in want:
                        self.assertTrue(same(cards[k], want[k]), f"{t} {lang} {k}:\n got  {norm(cards[k])}\n want {norm(want[k])}")

    def test_svgs_are_valid_and_sized(self):
        for t in TICKERS:
            for k, svg in render_all(t, "en").items():
                with self.subTest(ticker=t, card=k):
                    self.assertTrue(texts(svg))
                    size = ('width="1600"' if k == "wide" else 'width="1080"')
                    self.assertIn(size, svg[:300])


if __name__ == "__main__":
    unittest.main()
