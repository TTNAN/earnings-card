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

PNG export uses whatever fonts are installed. For `serif` install Source Serif 4 + Noto Serif SC; for `mono` install JetBrains Mono.
