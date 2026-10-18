#!/usr/bin/env python3
"""Static images for the web generator, rendered with render.py + headless Chromium (committed to docs/):

  docs/styles/thumbs/{style}.webp   style-picker thumbnails: the NVDA cover (zh, 4:5) in each of the 12 styles
  docs/og.png                       1200x630 share image (Open Graph / Twitter summary_large_image)
  docs/favicon.svg, docs/favicon-32.png, docs/apple-touch-icon.png (180x180)   the brand mark

  pip install playwright pillow   # Chromium: CHROMIUM=/path/to/chromium, default /usr/bin/chromium
  python3 tools/build_assets.py [--only thumbs|og|icons]

Needs the card fonts installed locally (Inter, Noto Sans/Serif SC, Source Serif 4, JetBrains Mono),
since the SVGs name them by family. Rerun after a style or the cover layout changes.
"""
import asyncio, io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "earnings-card", "scripts"))
import render as R  # noqa: E402

DOCS = os.path.join(ROOT, "docs")
CHROMIUM = os.environ.get("CHROMIUM", "/usr/bin/chromium")
STYLES = [k for k in R.THEMES if k not in ("paper", "ink")]
THUMB = (168, 210)   # 2x of the ~84x105 px chip

# the brand mark: three rising bars, the last one in the gold accent
MARK = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#151515"/>'
        '<rect x="13" y="35" width="10" height="16" rx="2" fill="#F3F0EA"/>'
        '<rect x="27" y="26" width="10" height="25" rx="2" fill="#F3F0EA"/>'
        '<rect x="41" y="14" width="10" height="37" rx="2" fill="#D9A65E"/></svg>')


def nvda():
    rec = json.load(open(os.path.join(DOCS, "data", "NVDA.json"), encoding="utf-8"))
    return R.period_record(rec["quarter"])


def cover(style, headline=""):
    d = nvda()
    t = R.build_style({"base": style})
    R.CURRENT_PAGE = ""
    return R.render_cards(d, "zh", t, ["cover"], "4:5", headline)[0][1].replace("__PAGE__", "")


def webp(png, size=None):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if size and im.size != size:
        im = im.resize(size, Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "WEBP", quality=84, method=6)
    return out.getvalue()


async def shoot(browser, html, w, h, scale=1):
    pg = await browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
    await pg.set_content(html)
    await pg.evaluate("document.fonts.ready")
    await pg.wait_for_timeout(150)
    png = await pg.screenshot(clip={"x": 0, "y": 0, "width": w, "height": h})
    await pg.close()
    return png


def page(body, css=""):
    return f"<!doctype html><html><head><meta charset=utf-8><style>html,body{{margin:0}}{css}</style></head><body>{body}</body></html>"


async def thumbs(b):
    os.makedirs(os.path.join(DOCS, "styles", "thumbs"), exist_ok=True)
    w, h = THUMB
    for st in STYLES:
        svg = cover(st).replace("<svg ", f'<svg style="display:block;width:{w}px;height:{h}px" ', 1)
        png = await shoot(b, page(svg), w, h)
        path = os.path.join(DOCS, "styles", "thumbs", f"{st}.webp")
        open(path, "wb").write(webp(png, THUMB))
        print(path, os.path.getsize(path), "bytes")


async def og(b):
    head = (R.headline_ideas(nvda(), "zh") or [""])[0]
    front = cover("light", head)
    back = cover("dark")
    sz = lambda s, w, h: s.replace("<svg ", f'<svg style="display:block;width:{w}px;height:{h}px" ', 1)
    css = """body{width:1200px;height:630px;background:#F3F0EA;font-family:Inter,'Noto Sans SC',sans-serif;color:#151515;position:relative;overflow:hidden}
      .l{position:absolute;left:72px;top:0;bottom:0;width:560px;display:flex;flex-direction:column;justify-content:center}
      .b{display:flex;align-items:center;gap:14px;font-weight:800;font-size:30px;letter-spacing:-.02em}
      .b svg{width:48px;height:48px}
      h1{font-family:'Noto Serif SC','Source Serif 4',serif;font-weight:700;font-size:64px;line-height:1.15;margin:34px 0 18px;letter-spacing:-.01em}
      p{margin:0;font-size:25px;line-height:1.55;color:#5F5A51;font-weight:500}
      .u{margin-top:34px;font-size:22px;font-weight:700;color:#8C6A3F;letter-spacing:.01em}
      .c{position:absolute;box-shadow:0 18px 50px #0000002e;border-radius:10px;overflow:hidden}
      .c1{left:880px;top:38px;transform:rotate(5deg)}
      .c2{left:700px;top:46px;transform:rotate(-3deg)}
      .rule{position:absolute;left:0;right:0;bottom:0;height:10px;background:#151515}"""
    body = (f'<div class="c c1">{sz(back, 344, 430)}</div><div class="c c2">{sz(front, 432, 540)}</div>'
            f'<div class="l"><div class="b">{MARK}<span>earnings-card</span></div>'
            '<h1>输入美股代码<br>一键生成财报卡</h1>'
            '<p>季报 · 年报 · 12 种风格 · 4 种比例<br>数据来自 SEC EDGAR 官方财报，免费开源</p>'
            '<div class="u">earningscard.tech</div></div><div class="rule"></div>')
    png = await shoot(b, page(body, css), 1200, 630)
    path = os.path.join(DOCS, "og.png")
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.save(path, "PNG", optimize=True)
    print(path, im.size, os.path.getsize(path), "bytes")


async def icons(b):
    open(os.path.join(DOCS, "favicon.svg"), "w").write(MARK + "\n")
    for name, px, pad in (("favicon-32.png", 32, 0), ("apple-touch-icon.png", 180, 0)):
        mark = MARK.replace("<svg ", f'<svg style="display:block;width:{px}px;height:{px}px" ', 1)
        if name.startswith("apple"):   # iOS rounds the corners itself: a full-bleed square
            mark = mark.replace('rx="14" ', "")
        png = await shoot(b, page(mark, "body{background:transparent}"), px, px)
        open(os.path.join(DOCS, name), "wb").write(png)
        print(name, os.path.getsize(os.path.join(DOCS, name)), "bytes")


async def main():
    from playwright.async_api import async_playwright
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])
        if only in ("", "thumbs"):
            await thumbs(b)
        if only in ("", "og"):
            await og(b)
        if only in ("", "icons"):
            await icons(b)
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
