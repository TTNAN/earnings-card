"""Contrast: text, bars and lines stand out from what is painted behind them, in every style.

The full sweep (all fixtures x ratios x languages) is tools/check_contrast.py; this runs a representative slice
of it (every style + the colour-override variants, every card) so a regression fails the suite."""
import os, sys, unittest
from helpers import ROOT
import render as R

sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_contrast as CC


class Contrast(unittest.TestCase):
    def test_every_style_every_card_passes(self):
        n, fails = CC.sweep(["NVDA", "JPM"], ratios=["4:5", "16:9"])
        self.assertGreater(n, 1000)
        self.assertEqual(fails, [], "\n".join(fails[:40]))

    def test_semantic_colours_follow_a_dark_page(self):
        # a light style recoloured onto near-black: its dark green / red get brighter, same hue
        t = R.fit_contrast(R.recolor(R.THEMES["light"], bg="#121212", ink="#F2EFE8"))
        for k in ("up", "down", "sub"):
            self.assertGreaterEqual(R.contrast(t[k], "#121212"), 4.5, k)
        self.assertGreater(R._lum(t["up"]), R._lum(R.THEMES["light"]["up"]))
        self.assertGreaterEqual(R.contrast(t["bar"], "#121212"), 3)

    def test_passing_colours_are_kept(self):
        # bloomberg's orange / blue / green already read on black: untouched
        b = R.THEMES["bloomberg"]
        t = R.fit_contrast(b)
        for k in ("ink", "up", "down", "hi", "a2"):
            self.assertEqual(t[k], b[k], k)

    def test_latest_bar_stays_distinct(self):
        for name in [k for k in R.THEMES if k not in ("paper", "ink")]:
            t = R.fit_contrast(R.THEMES[name])
            cols = R.bar_colors(t, 8)
            L0, L1 = R._lab(cols[0]), R._lab(cols[-1])
            dE = sum((a - b) ** 2 for a, b in zip(L0, L1)) ** 0.5
            with self.subTest(style=name):
                self.assertGreater(dE, 25)   # CIE76: clearly different at a glance

    def test_label_colour_follows_what_is_behind(self):
        self.assertEqual(R.ink_on("#000000", "#FFFFFF", "#000000"), "#FFFFFF")
        light = R.ink_on("#2C2C2E", "#3A3A3A", "#F5F5F7")      # dark label on a dark bar -> the light one
        self.assertGreaterEqual(R.contrast(light, "#2C2C2E"), 4.5)
        self.assertGreater(R._lum(light), 0.5)
        dark = R.ink_on("#F4F1EA", "#9A958B", "#151515", 7)    # muted label on paper -> darker, same hue
        self.assertGreaterEqual(R.contrast(dark, "#F4F1EA"), 7)


if __name__ == "__main__":
    unittest.main()
