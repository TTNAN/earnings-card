"""Design system rules: page numbers n/N over the whole set, one change indicator, restrained charts,
one shared masthead, serif display titles on the editorial styles."""
import json, re, unittest

from helpers import load, opt, texts
import render as R

SET8 = ["cover", "poster", "mix", "profit", "trend", "cash", "guide", "wide"]
STYLES = [k for k in R.THEMES if k not in ("paper", "ink")]


def page_no(svg):
    m = [s for s in texts(svg) if re.fullmatch(r"\d+/\d+", s)]
    return m[0] if m else None


class Numbering(unittest.TestCase):
    def setUp(self):
        self.d = load("NVDA.json")
        self.g = load("NVDA-guide-zh.json")

    def test_every_card_is_n_of_N(self):
        cards = R.render_cards(self.d, "zh", "light", SET8, "4:5", "标题", self.g)
        self.assertEqual([n for n, _ in cards], SET8)
        self.assertEqual([page_no(s) for _, s in cards], [f"{i}/8" for i in range(1, 9)])   # wide included

    def test_only_keeps_the_full_set_count(self):
        names = R.card_names(self.d, SET8, "4:5", self.g)
        for i in range(len(names)):
            out = json.loads(R.web_render(json.dumps(self.d), json.dumps(
                {"lang": "zh", "cards": SET8, "guidance": self.g, "only": i})))
            self.assertEqual(page_no(out["cards"][0]["svg"]), f"{i + 1}/{len(names)}")

    def test_single_card_has_no_number(self):
        (_, svg), = R.render_cards(self.d, "zh", "light", ["cover"], "4:5")
        self.assertIsNone(page_no(svg))

    def test_footer_is_small_and_light(self):
        (_, svg), _ = R.render_cards(self.d, "en", "light", ["cover", "profit"], "4:5")
        el = re.search(r'<text [^>]*font-size="(\d+)" font-weight="(\d+)" fill="([^"]+)"[^>]*><tspan[^>]*>earnings-card<', svg)
        self.assertLessEqual(int(el.group(1)), 16)
        self.assertLessEqual(int(el.group(2)), 500)
        self.assertEqual(el.group(3), R.THEMES["light"]["sub"])


class ChangeIndicator(unittest.TestCase):
    def test_no_filled_pills_anywhere(self):
        """Change marks are coloured text + a triangle on every card and style: never text knocked out of a
        filled badge (text drawn in the page colour), the old solid YoY pill."""
        d, g = load("NVDA.json"), load("NVDA-guide-en.json")
        for st in STYLES:
            t = R.build_style({"base": st})
            for name, svg in R.render_cards(d, "en", t, [n for n in R.DEFAULT_CARDS + R.EXTRA_CARDS if n != "post"], "4:5", "Head", g):   # post: the avatar initial is knocked out on purpose
                with self.subTest(style=st, card=name):
                    self.assertNotIn(f'fill="{t["bg"]}" letter-spacing', svg)

    def test_yoy_mark_is_value_plus_light_label(self):
        d = load("NVDA.json")
        t = R.THEMES["light"]
        svg = R.card_cover(d, R.L["en"], "en", t, "Head")
        self.assertRegex(svg, r'<polygon points="[^"]+" fill="%s"/>' % t["up"])
        self.assertIn(f'font-weight="700" fill="{t["up"]}"', svg)
        self.assertRegex(svg, r'font-weight="400" fill="%s"[^>]*><tspan[^>]*>YoY<' % t["sub"])

    def test_up_colour_is_ink_green_on_paper(self):
        up = R.THEMES["light"]["up"]
        r, g, b = R._hex(up)
        self.assertTrue(g > r and g > b and max(r, g, b) < 0x80, up)   # a deep green, not a bright one
        self.assertGreaterEqual(R.contrast(up, R.THEMES["light"]["bg"]), 4.5)


class Charts(unittest.TestCase):
    def setUp(self):
        self.d = load("NVDA.json")

    def test_bars_label_first_and_latest_only(self):
        svg = R.card_cover(self.d, R.L["zh"], "zh", R.THEMES["light"], "标题")
        tx = texts(svg)
        tr = self.d["trend"]
        labels = [R.plabel(q) for q in tr]
        self.assertIn(labels[0], tx)
        self.assertIn(labels[-1], tx)
        for lab in labels[1:-1]:
            self.assertNotIn(lab, tx)
        vals = [R.unit(q["revenue"], "zh") for q in tr]
        self.assertEqual(sum(1 for v in vals[1:-1] if v in tx), 0)

    def test_recent_bars_step_deeper(self):
        t = R.THEMES["light"]
        cols = R.bar_colors(t, 8)
        self.assertEqual(cols[-1], t.get("hi", t["ink"]))
        lum = [R._lum(c) for c in cols]
        self.assertTrue(lum[0] == lum[4] > lum[5] > lum[6] > lum[7])

    def test_line_chart_has_no_dot_per_point(self):
        svg = R.card_trend(self.d, R.L["en"], "en", R.THEMES["light"])
        self.assertLessEqual(svg.count("<circle"), 2 * 3)   # a start mark and an end dot per series
        self.assertEqual(len(re.findall(r'<circle [^>]*r="12"', svg)), 3)

    def test_waterfall_layers(self):
        t = R.THEMES["light"]
        svg = R.card_profit(self.d, R.L["en"], "en", t)
        self.assertIn(f'fill="{R.fit_contrast(t)["cool"]}"', svg)     # costs: cool grey (held to 3:1 on the page)
        self.assertIn(f'fill="{t["a2"]}"', svg)       # net income: the warm accent
        self.assertIn(f'fill="{t["up"]}"', svg)       # the positive other-income step


class TableRows(unittest.TestCase):
    """Mix and waterfall rows read in two levels: the amount as a hero-style figure, share / YoY small and grey."""
    def size_of(self, svg, s):
        return int(re.search(r'font-size="(\d+)"[^>]*><tspan[^>]*>%s<' % re.escape(s), svg).group(1))

    def test_mix_amount_leads(self):
        d = load("NVDA.json")
        t = R.THEMES["light"]
        for ratio in R.RATIOS:
            (_, svg), = R.render_cards(d, "en", "light", ["mix"], ratio)
            with self.subTest(ratio=ratio):
                amount = max(int(m) for m in re.findall(r'data-fig="[^"]+"[^>]*font-size="(\d+)"', svg))
                share = int(re.search(r'font-size="(\d+)" font-weight="400" fill="' + t["sub"] + r'"[^>]*><tspan[^>]*>\d+% of revenue<', svg).group(1))
                self.assertGreaterEqual(amount, share * 1.6)
                self.assertRegex(svg, r'font-weight="600" fill="%s"[^>]*><tspan[^>]*>\+' % t["up"])   # YoY: lighter mark

    def test_profit_amount_is_a_figure(self):
        svg = R.card_profit(load("NVDA.json"), R.L["zh"], "zh", R.THEMES["light"])
        self.assertGreaterEqual(self.size_of(svg, "962.2"), 34)
        self.assertLess(self.size_of(svg, "亿"), self.size_of(svg, "962.2") * 0.7)   # small unit, like num()
        self.assertLessEqual(self.size_of(svg, "25.0% "), 17)


class Masthead(unittest.TestCase):
    def test_same_header_on_every_card(self):
        d, g = load("NVDA.json"), load("NVDA-guide-en.json")
        for name, svg in R.render_cards(d, "en", "light", SET8, "4:5", "Head", g):
            with self.subTest(card=name):
                first = texts(svg)[:3]
                self.assertEqual(first[0], "NVDA")
                self.assertTrue(first[2].startswith(d["fiscal_label"]), first)

    def test_hero_unit_is_smaller_than_digits(self):
        svg = R.card_cover(load("NVDA.json"), R.L["zh"], "zh", R.THEMES["light"], "标题")
        big = int(re.search(r'font-size="(\d+)"[^>]*><tspan[^>]*>962\.2<', svg).group(1))
        unit_ = int(re.search(r'font-size="(\d+)"[^>]*><tspan[^>]*>亿<', svg).group(1))
        self.assertLess(unit_, big * 0.7)

    def test_titles_serif_on_editorial_styles(self):
        d = load("NVDA.json")
        for st in ("light", "dark", "morandi"):
            svg = R.card_profit(d, R.L["zh"], "zh", R.build_style({"base": st}))
            self.assertIn(f'<tspan font-family="{R.SERIF_SC}">营收是怎么变成利润的', svg, st)


if __name__ == "__main__":
    unittest.main()
