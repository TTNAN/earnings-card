# Custom styles · 自定义风格

`render.py --style my-style.json` starts from a built-in style (`base`) and overrides only the keys you set.

| Key | What it changes |
| --- | --- |
| `base` | `light` (paper), `dark` (ink), `mono`, `terminal`, `salmon`, `pop`, `bloomberg`, `keynote`, `neon`, `vintage`, `morandi`, `glass` |
| `font` | `sans`, `serif` or `mono` (Latin + Chinese pairs) |
| `bg` `ink` `sub` | background, main text, secondary text |
| `card` `faint` `bar` | metric boxes, hairlines, chart bars |
| `hi` | the highlighted (latest) bar |
| `up` `down` | good / bad numbers |
| `a1` `a2` `a3` | the three margin lines |
| `palette` | segment colors on the revenue-mix card |
| `round` | corner radius multiplier, `0` = square |
| `stroke` | box outline width, `0` = none |
| `card_stroke` `card_stroke_opacity` `card_opacity` | box outline colour / opacity, box fill opacity (translucent cards) |
| `bg_grad` | a list of 2-3 colours for a diagonal gradient page (as in `glass`); a custom `bg` in the web app turns it off |
| `handle` | your @handle, printed in the footer (and as the author on the `post` card) |
| `avatar` | a square image next to the handle (path relative to the JSON) |

**Contrast is enforced.** Whatever colours you pick, the renderer keeps them legible on your background (WCAG ratios):
text and the up / down colours reach 4.5:1 against the page and the boxes, bars / margin lines / `hi` 3:1, segment colours 1.5:1,
and small chart value labels 7:1. A colour that already passes is used as is; one that doesn't is moved one step lighter (dark page)
or darker (light page) with its hue kept, so a dark green `up` on a black page comes out as a brighter green. The latest bar is also
kept clearly different from the older ones. `python3 tools/check_contrast.py` sweeps every style and card.

PNG export uses whatever fonts are installed. For `serif` install Source Serif 4 + Noto Serif SC; for `mono` install JetBrains Mono.
