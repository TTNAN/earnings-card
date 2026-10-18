#!/usr/bin/env python3
"""Fetch quarterly or full-year financials for a US-listed ticker from SEC EDGAR (free, no API key).

Usage: python3 fetch_sec.py NVDA [--period quarter|annual] [--out data.json]
quarter (default): the latest quarter's key metrics, YoY changes and an 8-quarter trend.
annual: the latest fiscal year (10-K) with the same fields, YoY vs the prior year and a 5-year trend.
"""
import json, os, sys, time, urllib.request
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


def quarterly(facts, tags):
    """Return {end_date: (value, start, filed, form)} of 3-month values, deriving Q4 from FY - Q1..Q3."""
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


def annual(facts, tags):
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


def build(ticker, period="quarter"):
    """period: "quarter" (latest 10-Q/10-K quarter, 8-quarter trend) or "annual" (latest fiscal year, 5-year trend)."""
    yearly = period == "annual"
    cik, title = lookup_cik(ticker)
    data = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", f"{cik}.json")
    facts = data["facts"].get("us-gaap", {})
    series = annual if yearly else quarterly
    s = {k: series(facts, v) for k, v in TAGS.items()}
    if not s["revenue"]:
        raise SystemExit(f"No {'annual' if yearly else 'quarterly'} revenue found for this company.")
    end = max(s["revenue"])
    rev = s["revenue"][end]
    if not s["gross_profit"] and s["cost_of_revenue"]:
        s["gross_profit"] = {e: (v[0] - (_match(s["cost_of_revenue"], e) or 0),) + v[1:]
                             for e, v in s["revenue"].items() if _match(s["cost_of_revenue"], e) is not None}

    def val(k, e=end):
        return _match(s[k], e) if s[k] else None

    def margin(k, e=end):
        a, r = val(k, e), val("revenue", e)
        return a / r if a is not None and r else None

    prev_year = date.fromisoformat(end).replace(year=date.fromisoformat(end).year - 1).isoformat()
    trend_ends = sorted(s["revenue"])[-5:] if yearly else sorted(s["revenue"])[-8:]
    out = {
        "ticker": ticker.upper(),
        "period": period,
        "company": title,
        "period_start": rev[1],
        "period_end": end,
        "filed": rev[2],
        "form": rev[3],
        "fiscal_label": _fiscal_label(data, end, yearly),
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
        "trend": [{"end": e, "revenue": s["revenue"][e][0], "net_income": val("net_income", e),
                   "gross_margin": margin("gross_profit", e), "operating_margin": margin("operating_income", e),
                   "net_margin": margin("net_income", e),
                   "fcf": (val("ocf", e) - (val("capex", e) or 0)) if val("ocf", e) is not None else None,
                   **({"label": "FY" + (_fiscal_label(data, e, True)[2:] or e[:4])[-2:]} if yearly else {})}
                  for e in trend_ends],
        "source": f"SEC EDGAR · {rev[3]} filed {rev[2]}",
        "cik": cik, "accn": rev[4],
    }
    try:
        from segments import segments
        out["segments"] = segments(cik, rev[4], rev[1], end, yearly) if rev[4] else {}
    except Exception as e:  # segment data is a bonus; never fail the card for it
        out["segments"] = {}
        out["segments_error"] = str(e)
    return out


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
    res = build(sys.argv[1], per)
    if "--out" in sys.argv:
        json.dump(res, open(sys.argv[sys.argv.index("--out") + 1], "w"), indent=2, ensure_ascii=False)
    else:
        print(json.dumps(res, indent=2, ensure_ascii=False))
