import json, os, tempfile, unittest
from helpers import load
import render as R

STYLES = ["light", "dark", "mono", "terminal", "salmon", "pop", "bloomberg", "keynote", "neon", "vintage", "morandi", "glass"]


class Styles(unittest.TestCase):
    def test_every_builtin_style_renders_every_card(self):
        d = load("NVDA.json")
        g = load("NVDA-guide-en.json")
        for st in STYLES:
            t = R.resolve_style(st)
            with self.subTest(style=st):
                for fn in (R.card_profit, R.card_trend, R.card_cash):
                    self.assertIn(t["bg"], fn(d, R.L["en"], "en", t))
                self.assertIn(t["bg"], R.card_cover(d, R.L["en"], "en", t, "x"))
                self.assertIn(t["bg"], R.card_mix(d, R.L["en"], "en", t, {}))
                self.assertIn(t["bg"], R.card_guide(d, R.L["en"], "en", t, g))

    def test_aliases(self):
        self.assertEqual(R.resolve_style("paper")["bg"], R.THEMES["light"]["bg"])
        self.assertEqual(R.resolve_style("ink")["bg"], R.THEMES["dark"]["bg"])

    def test_custom_style_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.png"), "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")
            p = os.path.join(tmp, "s.json")
            with open(p, "w") as f:
                json.dump({"base": "dark", "font": "serif", "bg": "#0F1A2B", "handle": "@me", "avatar": "a.png", "round": 0}, f)
            t = R.resolve_style(p)
            self.assertEqual(t["bg"], "#0F1A2B")
            self.assertEqual(t["ink"], R.THEMES["dark"]["ink"])          # inherited from base
            self.assertTrue(t["avatar"].startswith("data:image/png;base64,"))
            svg = R.card_cover(load("NVDA.json"), R.L["en"], "en", t, "x")
            self.assertIn("@me", svg)
            self.assertIn("Source Serif 4", svg)
            self.assertIn("<image", svg)
            self.assertNotIn('rx="18"', svg)                              # round = 0
        R.apply_style(R.THEMES["light"])


if __name__ == "__main__":
    unittest.main()
