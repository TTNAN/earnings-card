---
name: earnings-card
description: Turn a US stock ticker into a beautiful, shareable earnings card (SVG/HTML/PNG) built from official SEC filings. Use when the user asks for an earnings card, 财报卡, 财报一图流, a quarterly results summary image, or "how did <ticker> do last quarter" with a visual.
---

# Earnings Card · 财报卡

Make a set of up to seven editorial-quality cards (up to six portrait cards plus a landscape cover) for the latest reported quarter (or fiscal year) of a US-listed company. Data comes only from SEC EDGAR XBRL filings (free, no API key).

## Steps

1. Set a User-Agent with a contact email (SEC requires it), then fetch:
   ```bash
   export SEC_USER_AGENT="your-name your@email.com"
   python3 scripts/fetch_sec.py NVDA --out /tmp/NVDA.json
   ```
   For the annual report (10-K) instead of the latest quarter, add `--period annual` (when the user asks for 年报 / full year / FY). Same JSON fields, for the whole fiscal year: YoY is vs the prior year, the trend is 5 years, labels read FY2025 etc. The guidance card is quarterly only.
2. Read the JSON. Write ONE headline that a reader gets in two seconds:
   - Chinese: at most 18 characters. English: at most 40 characters.
   - Use only numbers in the JSON (revenue_yoy, gross_margin vs gross_margin_prev, net_income_yoy, eps_yoy, trend). No guidance, no price talk, no buy/sell opinions, no causes you cannot see in the data.
   - Lead with the most surprising contrast, e.g. 「营收同比翻倍，毛利率稳在 75%」 or 「营收回暖，但利润还在原地踏步」.
3. Render:
   ```bash
   python3 scripts/render.py /tmp/NVDA.json --out ./NVDA-card --headline "营收同比翻倍，毛利率稳在 75%" --lang zh --png
   ```
   This writes up to seven cards (mix and guide are skipped when there is no data for them): `-1-cover` (headline, revenue, 8-quarter bars, 4 key metrics), `-2-mix` (revenue by business and by region, read from the filing's own XBRL, with share and YoY; skipped when the filing has no breakdown), `-3-profit` (waterfall from revenue to net income), `-4-trend` (8 quarters of gross/operating/net margin + net income), `-5-cash` (operating cash flow, capex, free cash flow, buybacks, dividends, cash pile), `-6-guide` (management's next-quarter outlook, and last quarter's outlook vs what actually happened; only with `--guidance`), `-7-wide` (1600×900 for X / slides), plus one HTML page with all of them.
   For Chinese cards, translate segment names: write a JSON map from the English labels in `segments` (e.g. `{"Data Center": "数据中心", "Greater China": "大中华区"}`) and pass `--labels map.json`. Keep product names like iPhone, AWS, Mac as they are.
   Guidance: run `python3 scripts/fetch_guidance.py data.json --out guidance_raw.json`. It prints the outlook text from this quarter's earnings release (outlook for next quarter) and the previous one (outlook for this quarter). Read it and write `guidance.json`:
   ```json
   {"next": {"period": "FY2027 Q3", "items": [
       {"metric": "营收", "low": 105.84e9, "high": 110.16e9, "base": 96.221e9, "display": "$1,080亿 ±2%"},
       {"metric": "GAAP 毛利率", "low": 0.735, "high": 0.745, "unit": "pct", "base": 0.7498},
       {"metric": "GAAP 营业费用", "low": 9.2e9, "high": 9.2e9, "base": 8.406e9, "lower_is_better": true}]},
    "prior": {"period": "FY2027 Q2", "items": [
       {"metric": "营收", "low": 89.18e9, "high": 92.82e9, "actual": 96.221e9}]},
    "note": "one short caveat the release states, e.g. what the outlook excludes"}
   ```
   Rules: only numbers the release states (turn "X plus or minus 2%" into low/high; a point estimate has low = high). `base` and `actual` come from data.json (same GAAP basis as the guidance; skip a metric whose basis doesn't match, e.g. non-GAAP only). Up to 4 next items, 3 prior items. If the release has no numeric outlook (Apple, Microsoft and Tesla give theirs on the call), skip `--guidance`; the card is left out and say so in one line.
   Pick a subset with `--cards cover,profit` when the user only wants some.
   Options: `--ratio 4:5|1:1|9:16|16:9` (default 4:5 portrait 1080×1350; 1:1 square 1080×1080 for Weibo/Instagram; 9:16 story 1080×1920; 16:9 landscape 1920×1080 for X/slides, where the cover is the landscape layout and `wide` is dropped), `--lang zh|en` (match the user's language), `--style light|dark|mono|terminal|salmon|pop` (paper, ink, Swiss black & white, Bloomberg-style terminal, salmon newspaper, Xiaohongshu pop; pick the one the user asks for, default light) or `--style my-style.json` for the user's own colors, font, @handle and avatar (see `styles/README.md`), `--png` (needs `pip install cairosvg`; otherwise open the .html and screenshot).
4. Give the user the PNG (or HTML) and one line on what stands out. Mention it is GAAP data from the 10-Q/10-K, not company-adjusted figures.

## Limits

- US-listed companies that file with the SEC only (no A-shares/HK yet).
- GAAP numbers; company "adjusted" EPS in press releases can differ.
- Fourth quarters are derived as full year minus Q1–Q3 (marked "derived" in the source field).
- The card shows the latest quarter in SEC filings; results announced today may take a day or two to appear.
- No-install option for users: the online generator at https://ttnan.github.io/earnings-card/ (precomputed tickers only, S&P 100 to start).
