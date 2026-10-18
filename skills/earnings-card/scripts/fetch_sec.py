#!/usr/bin/env python3
"""Fetch quarterly or full-year financials for a US-listed ticker from SEC EDGAR (free, no API key).

Usage: python3 fetch_sec.py NVDA [--period quarter|annual] [--fy 2026 [--fq 2] | --period-end 2025-10-26]
                            [--list] [--out data.json]
quarter (default): the latest quarter's key metrics, YoY changes and an 8-quarter trend.
annual: the latest fiscal year (10-K) with the same fields, YoY vs the prior year and a 5-year trend.
--fy/--fq or --period-end pick an earlier period instead of the latest (fiscal years as the company
numbers them, e.g. --fy 2026 --fq 2 = "FY2026 Q2"); the trend then ends at that period.
--list prints the periods available (newest last) instead of the card data.
"""
import json, os, re, sys, time, urllib.request
from datetime import date

UA = os.environ.get("SEC_USER_AGENT", "earnings-card-skill earnings-card@users.noreply.github.com")
CACHE = os.environ.get("EC_CACHE", os.path.expanduser("~/.cache/earnings-card"))
# SEC allows at most 10 requests a second per client; stay well under it.
MIN_INTERVAL = float(os.environ.get("EC_MIN_INTERVAL", "0.15"))
_last = [0.0]


def _open(url, timeout):
    wait = _last[0] + MIN_INTERVAL - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    return urllib.request.urlopen(req, timeout=timeout)

TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense"],
    "gross_profit": ["GrossProfit"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic"],
    "rnd": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "sga": ["SellingGeneralAndAdministrativeExpense"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "buyback": ["PaymentsForRepurchaseOfCommonStock"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
}
INSTANT = {
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "securities": ["MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent", "ShortTermInvestments"],
}


def _get(url, cache_name, max_age=6 * 3600):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age:
        return json.load(open(path))
    with _open(url, 30) as r:
        data = json.loads(r.read())
    json.dump(data, open(path, "w"))
    return data


def _get_raw(url, cache_name, max_age=30 * 86400):
    """Raw bytes with an on-disk cache (filings never change once filed)."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, cache_name)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age:
        return open(path, "rb").read()
    with _open(url, 60) as r:
        data = r.read()
    open(path, "wb").write(data)
    return data


def lookup_cik(ticker):
    t = _get("https://www.sec.gov/files/company_tickers.json", "tickers.json", 7 * 86400)
    want = ticker.upper().replace(".", "-")   # BRK.B is BRK-B in SEC's list
    for row in t.values():
        if row["ticker"].upper() == want:
            return int(row["cik_str"]), row["title"]
    raise SystemExit(f"Ticker {ticker} not found in SEC list (US-listed companies only).")


def _days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


FILING_FORMS = ("10-Q", "10-K", "20-F", "40-F")


def _note_origin(origins, x):
    """Remember the first periodic filing that reported a period ending x["end"] (the original, not a later comparative)."""
    if origins is None or not x.get("form", "").startswith(FILING_FORMS):
        return
    cur = origins.get(x["end"])
    if cur is None or x.get("filed", "") < cur[0]:
        origins[x["end"]] = (x.get("filed", ""), x.get("form", ""), x.get("accn", ""))


def quarterly(facts, tags, origins=None):
    """Return {end_date: (value, start, filed, form)} of 3-month values, deriving Q4 from FY - Q1..Q3.

    origins: optional dict, filled with {end: (filed, form, accn)} of the filing that first reported each period."""
    best = None
    for tag in tags:
        node = facts.get(tag)
        if not node:
            continue
        units = node["units"]
        series = units.get("USD") or units.get("USD/shares") or next(iter(units.values()))
        latest_end = max(x["end"] for x in series)
        if best is None or latest_end > best[0]:
            best = (latest_end, series)
    if not best:
        return {}
    series = best[1]
    q, ytd = {}, {}
    for x in series:
        if "start" not in x:
            continue
        d = _days(x["start"], x["end"])
        rec = (x["val"], x["start"], x.get("filed", ""), x.get("form", ""), x.get("accn", ""))
        if 80 <= d <= 100 or 170 <= d <= 380:
            _note_origin(origins, x)
        if 80 <= d <= 100:
            if x["end"] not in q or rec[2] > q[x["end"]][2]:
                q[x["end"]] = rec
        elif 170 <= d <= 380:
            k = (x["start"], x["end"])
            if k not in ytd or rec[2] > ytd[k][2]:
                ytd[k] = rec
    # Cash-flow items (and 10-K fourth quarters) are reported year-to-date: difference consecutive periods.
    by_start = {}
    for (st, en), rec in ytd.items():
        by_start.setdefault(st, []).append((en, rec))
    for st, items in by_start.items():
        items.sort()
        first_q = [(e, v) for e, v in q.items() if v[1] == st]
        chain = sorted(first_q[:1] + items)
        for (e0, r0), (e1, r1) in zip(chain, chain[1:]):
            if e1 not in q and 80 <= _days(e0, e1) <= 100:
                tag = r1[3] if "derived" in r1[3] else r1[3] + " (derived)"
                q[e1] = (r1[0] - r0[0], e0, r1[2], tag, r1[4])
    return q


def annual(facts, tags, origins=None):
    """Return {end_date: (value, start, filed, form, accn)} of full fiscal-year values (10-K)."""
    best = None
    for tag in tags:
        node = facts.get(tag)
        if not node:
            continue
        units = node["units"]
        series = units.get("USD") or units.get("USD/shares") or next(iter(units.values()))
        yearly = [x for x in series if "start" in x and 350 <= _days(x["start"], x["end"]) <= 380]
        if not yearly:
            continue
        latest_end = max(x["end"] for x in yearly)
        if best is None or latest_end > best[0]:
            best = (latest_end, yearly)
    if not best:
        return {}
    out = {}
    for x in best[1]:
        _note_origin(origins, x)
        rec = (x["val"], x["start"], x.get("filed", ""), x.get("form", ""), x.get("accn", ""))
        k10 = rec[3].startswith(("10-K", "20-F", "40-F"))
        cur = out.get(x["end"])
        cur_k10 = cur is not None and cur[3].startswith(("10-K", "20-F", "40-F"))
        if cur is None or (k10 and not cur_k10) or (k10 == cur_k10 and rec[2] > cur[2]):
            out[x["end"]] = rec
    return out


def _shift(end):
    d = date.fromisoformat(end)
    return date.fromordinal(d.toordinal() - 90).isoformat()


def instant(facts, tags, end, tol=10):
    for tag in tags:
        node = facts.get(tag)
        if not node:
            continue
        for x in next(iter(node["units"].values())):
            if "start" not in x and abs(_days(x["end"], end)) <= tol:
                return x["val"]
    return None


def _match(series, end, tol=10):
    """Find the value whose end date is within tol days of end."""
    for e, v in series.items():
        if abs(_days(e, end)) <= tol:
            return v[0]
    return None


def yoy(series, end):
    prev_end = date.fromisoformat(end)
    prev_end = prev_end.replace(year=prev_end.year - 1).isoformat()
    cur, prev = _match(series, end), _match(series, prev_end)
    if cur is None or prev in (None, 0):
        return None
    return (cur - prev) / abs(prev)


def load(ticker, period="quarter"):
    """Everything needed to build any period's record: company facts and the per-metric series."""
    yearly = period == "annual"
    cik, title = lookup_cik(ticker)
    data = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", f"{cik}.json",
                float(os.environ.get("EC_FACTS_MAX_AGE", 6 * 3600)))
    facts = data["facts"].get("us-gaap", {})
    series = annual if yearly else quarterly
    origins = {}
    s = {k: series(facts, v, origins if k == "revenue" else None) for k, v in TAGS.items()}
    if not s["revenue"]:
        raise SystemExit(f"No {'annual' if yearly else 'quarterly'} revenue found for this company.")
    if not s["gross_profit"] and s["cost_of_revenue"]:
        s["gross_profit"] = {e: (v[0] - (_match(s["cost_of_revenue"], e) or 0),) + v[1:]
                             for e, v in s["revenue"].items() if _match(s["cost_of_revenue"], e) is not None}
    ctx = {"ticker": ticker, "period": period, "yearly": yearly, "cik": cik, "title": title, "data": data,
           "facts": facts, "s": s, "origins": origins}
    ctx["labels"] = fiscal_labels(data, sorted(s["revenue"]), yearly)
    return ctx


def fiscal_labels(data, ends, yearly):
    """{end: "FY2026 Q2" / "FY2026"} for every period, counted back from the latest one's label.

    companyfacts tags each value with the fiscal year of the filing that reported it, so an older period
    repeated as a comparative in a later filing carries the later year. The latest period is only in its
    own filing, so its label is right; earlier ones are counted back from it by date."""
    if not ends:
        return {}
    last = ends[-1]
    lab = _fiscal_label(data, last, yearly)
    m = re.match(r"FY(\d{4})(?: Q(\d))?$", lab or "")
    if not m:
        return {e: _fiscal_label(data, e, yearly) for e in ends}
    fy, fq = int(m.group(1)), int(m.group(2) or 4)
    out = {}
    for e in ends:
        if yearly:
            out[e] = f"FY{fy - round(_days(e, last) / 365.25)}"
        else:
            idx = fy * 4 + (fq - 1) - round(_days(e, last) / 91.31)
            out[e] = f"FY{idx // 4} Q{idx % 4 + 1}"
    return out


def periods(ctx):
    """[(period_end, fiscal_label)] of every period with revenue, oldest first."""
    return [(e, (ctx.get("labels") or {}).get(e) or _fiscal_label(ctx["data"], e, ctx["yearly"])) for e in sorted(ctx["s"]["revenue"])]


def pick_end(ctx, period_end=None, fy=None, fq=None):
    """The period end to build: the latest by default, else the one matching a date or a fiscal year/quarter."""
    ends = sorted(ctx["s"]["revenue"])
    if period_end:
        hit = [e for e in ends if abs(_days(e, period_end)) <= 10]
        if not hit:
            raise SystemExit(f"No {ctx['period']} ending near {period_end}. Available: {', '.join(ends[-8:])}")
        return hit[-1]
    if fy:
        want = f"FY{int(fy)}" + ("" if ctx["yearly"] else f" Q{int(fq or 4)}")
        hit = [e for e, lab in periods(ctx) if lab == want]
        if not hit:
            have = ", ".join(lab or e for e, lab in periods(ctx)[-8:])
            raise SystemExit(f"No {want} in the filings. Latest available: {have}")
        return hit[-1]
    return ends[-1]


def build(ticker, period="quarter", period_end=None, fy=None, fq=None, ctx=None, with_segments=True):
    """period: "quarter" (latest 10-Q/10-K quarter, 8-quarter trend) or "annual" (latest fiscal year, 5-year trend).

    period_end / fy (+ fq) pick an earlier period; its trend window ends at that period."""
    ctx = ctx or load(ticker, period)
    end = pick_end(ctx, period_end, fy, fq)
    return record(ctx, end, with_segments)


def record(ctx, end, with_segments=True):
    """The card data for the period ending `end` (one of ctx["s"]["revenue"]'s keys)."""
    ticker, period, yearly, data, facts, s = (ctx[k] for k in ("ticker", "period", "yearly", "data", "facts", "s"))
    cik, title = ctx["cik"], ctx["title"]
    rev = s["revenue"][end]
    # filed / form / accession of the filing that first reported this period (a later 10-Q repeats it as a comparative)
    org = ctx["origins"].get(end)
    if org and org[0] <= rev[2]:
        form = org[1] + (" (derived)" if "derived" in rev[3] else "")
        rev = (rev[0], rev[1], org[0], form, org[2])

    def val(k, e=end):
        return _match(s[k], e) if s[k] else None

    def margin(k, e=end):
        a, r = val(k, e), val("revenue", e)
        return a / r if a is not None and r else None

    prev_year = date.fromisoformat(end).replace(year=date.fromisoformat(end).year - 1).isoformat()
    ends = [e for e in sorted(s["revenue"]) if e <= end]
    trend_ends = ends[-5:] if yearly else ends[-8:]
    out = {
        "ticker": ticker.upper(),
        "period": period,
        "company": title,
        "period_start": rev[1],
        "period_end": end,
        "filed": rev[2],
        "form": rev[3],
        "fiscal_label": (ctx.get("labels") or {}).get(end) or _fiscal_label(data, end, yearly),
        "revenue": rev[0],
        "revenue_yoy": yoy(s["revenue"], end),
        "gross_margin": margin("gross_profit"),
        "gross_margin_prev": margin("gross_profit", prev_year),
        "operating_income": val("operating_income"),
        "operating_margin": margin("operating_income"),
        "net_income": val("net_income"),
        "net_income_yoy": yoy(s["net_income"], end) if s["net_income"] else None,
        "eps": val("eps"),
        "eps_yoy": yoy(s["eps"], end) if s["eps"] else None,
        "rnd": val("rnd"), "sga": val("sga"), "tax": val("tax"),
        "cost_of_revenue": (rev[0] - val("gross_profit")) if val("gross_profit") is not None else None,
        "ocf": val("ocf"), "capex": val("capex"),
        "fcf": (val("ocf") - (val("capex") or 0)) if val("ocf") is not None else None,
        "buyback": val("buyback"), "dividends": val("dividends"),
        "cash": instant(facts, INSTANT["cash"], end), "securities": instant(facts, INSTANT["securities"], end),
        "trend": [trend_point(ctx, e) for e in trend_ends],
        # the same figures a year earlier (YoY columns) and one period earlier (sequential comparisons)
        "prev": compare_point(ctx, prev_year),
        "prev_q": compare_point(ctx, ends[-2]) if len(ends) > 1 and not yearly else None,
        "source": f"SEC EDGAR · {rev[3]} filed {rev[2]}",
        "cik": cik, "accn": rev[4],
    }
    if not with_segments:
        return out
    try:
        from segments import segments
        out["segments"] = segments(cik, rev[4], rev[1], end, yearly) if rev[4] else {}
    except Exception as e:  # segment data is a bonus; never fail the card for it
        out["segments"] = {}
        out["segments_error"] = str(e)
    return out


def compare_point(ctx, e):
    """Income-statement and cash-flow figures for the period ending near e (None when that period has no revenue)."""
    s = ctx["s"]

    def val(k):
        return _match(s[k], e) if s[k] else None

    rev = val("revenue")
    if rev is None:
        return None
    gp, oi, ni, ocf, capex = val("gross_profit"), val("operating_income"), val("net_income"), val("ocf"), val("capex")
    out = {"revenue": rev, "cost_of_revenue": rev - gp if gp is not None else None, "gross_profit": gp,
           "gross_margin": gp / rev if gp is not None and rev else None, "rnd": val("rnd"), "sga": val("sga"),
           "operating_income": oi, "operating_margin": oi / rev if oi is not None and rev else None,
           "tax": val("tax"), "net_income": ni, "net_margin": ni / rev if ni is not None and rev else None,
           "eps": val("eps"), "ocf": ocf, "capex": capex, "fcf": (ocf - (capex or 0)) if ocf is not None else None}
    return {k: v for k, v in out.items() if v is not None}


def trend_point(ctx, e):
    """One bar / line point of the trend charts, for the period ending e."""
    s, yearly, data = ctx["s"], ctx["yearly"], ctx["data"]

    def val(k):
        return _match(s[k], e) if s[k] else None

    def margin(k):
        a, r = val(k), val("revenue")
        return a / r if a is not None and r else None

    return {"end": e, "revenue": s["revenue"][e][0], "net_income": val("net_income"),
            "gross_margin": margin("gross_profit"), "operating_margin": margin("operating_income"),
            "net_margin": margin("net_income"),
            "fcf": (val("ocf") - (val("capex") or 0)) if val("ocf") is not None else None,
            **({"label": "FY" + ((ctx.get("labels") or {}).get(e) or _fiscal_label(data, e, True) or e[:4])[-2:]} if yearly else {})}


def _fiscal_label(data, end, yearly=False):
    """FY2027 Q2 for a quarter, FY2026 for a fiscal year (as the company numbers its years)."""
    for tag in TAGS["revenue"]:
        node = data["facts"].get("us-gaap", {}).get(tag)
        if not node:
            continue
        hits = [x for x in next(iter(node["units"].values()))
                if x["end"] == end and x.get("fy") and x.get("fp")]
        if yearly:
            hits = [x for x in hits if x["fp"] == "FY" and "start" in x and _days(x["start"], end) > 300]
        if hits:
            x = min(hits, key=lambda h: h.get("filed", ""))  # original filing, not a later comparative
            if yearly:
                return f"FY{x['fy']}"
            fp = x["fp"] if x["fp"] != "FY" else "Q4"
            return f"FY{x['fy']} {fp}"
    return f"FY{end[:4]}" if yearly else ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    per = sys.argv[sys.argv.index("--period") + 1] if "--period" in sys.argv else "quarter"
    if per not in ("quarter", "annual"):
        raise SystemExit("--period must be quarter or annual")
    arg = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    ctx = load(sys.argv[1], per)
    if "--list" in sys.argv:
        for e, lab in periods(ctx):
            print(f"{e}  {lab}")
        raise SystemExit(0)
    res = build(sys.argv[1], per, arg("--period-end"), arg("--fy"), arg("--fq"), ctx=ctx)
    if "--out" in sys.argv:
        json.dump(res, open(sys.argv[sys.argv.index("--out") + 1], "w"), indent=2, ensure_ascii=False)
    else:
        print(json.dumps(res, indent=2, ensure_ascii=False))
