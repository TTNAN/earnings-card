#!/usr/bin/env python3
"""Upcoming earnings dates for the supported tickers -> docs/data/calendar.json (the web page's 财报日历).

  python3 tools/build_calendar.py               # the next 14 days from today (UTC)
  python3 tools/build_calendar.py --days 21

Source: Nasdaq's public earnings calendar (api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD), free, no key;
it wants a browser User-Agent. Rows are kept only for tickers in docs/data/tickers.json.
Output: {"updated": "YYYY-MM-DD", "source": "nasdaq", "rows": [{"t", "date", "time"}]}, time = bmo | amc | "".
If every request fails the old file is left as it is (the page drops past dates itself), so one bad night
never empties the calendar.
"""
import argparse, json, os, sys, time, urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "calendar.json")
TICKERS = os.path.join(ROOT, "docs", "data", "tickers.json")
URL = "https://api.nasdaq.com/api/calendar/earnings?date={}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
TIMES = {"time-pre-market": "bmo", "time-after-hours": "amc"}


def norm(sym):
    """Nasdaq writes class shares as BRK.B, BRK/B or BRK-B; tickers.json uses BRK.B."""
    return (sym or "").strip().upper().replace("/", ".").replace("-", ".")


def parse_day(payload, day, supported):
    """Rows of one Nasdaq calendar response for the supported tickers: [{"t", "date", "time"}]."""
    rows = (((payload or {}).get("data") or {}).get("rows")) or []
    out = []
    for r in rows:
        t = norm(r.get("symbol"))
        if t in supported:
            out.append({"t": t, "date": day, "time": TIMES.get(r.get("time") or "", "")})
    return out


def merge(rows):
    """One row per ticker (its earliest upcoming date), sorted by date, then bmo before amc, then ticker."""
    best = {}
    for r in rows:
        if r["t"] not in best or r["date"] < best[r["t"]]["date"]:
            best[r["t"]] = r
    order = {"bmo": 0, "": 1, "amc": 2}
    return sorted(best.values(), key=lambda r: (r["date"], order.get(r["time"], 1), r["t"]))


def fetch(day, tries=3):
    req = urllib.request.Request(URL.format(day), headers={"User-Agent": UA, "Accept": "application/json",
                                                           "Accept-Language": "en-US,en;q=0.9"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - any network/JSON error: retry, then give up on this day
            err = e
            time.sleep(1.5 * (i + 1))
    raise err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    supported = {t for t, _ in json.load(open(TICKERS, encoding="utf-8"))}
    today = datetime.now(timezone.utc).date()
    rows, ok, failed = [], 0, []
    for i in range(a.days + 1):
        d = today + timedelta(days=i)
        if d.weekday() >= 5:   # no earnings calls on weekends
            continue
        day = d.isoformat()
        try:
            rows += parse_day(fetch(day), day, supported)
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed.append(f"{day}: {e}")
        time.sleep(0.4)
    if not ok:
        print("calendar: every request failed, keeping the old file;", "; ".join(failed[:3]))
        return 0
    out = {"updated": today.isoformat(), "source": "nasdaq", "rows": merge(rows)}
    old = None
    if os.path.exists(a.out):
        try:
            old = json.load(open(a.out, encoding="utf-8"))
        except ValueError:
            pass
    if old and old.get("rows") == out["rows"]:
        print(f"calendar: unchanged ({len(out['rows'])} rows)")
        return 0
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"calendar: {len(out['rows'])} rows from {ok} days" + (f"; failed {failed}" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
