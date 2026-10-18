#!/usr/bin/env python3
"""Precompute card data for the web generator (GitHub Pages can't call SEC from the browser).

  python3 tools/build_data.py                    # every ticker in tools/tickers.txt
  python3 tools/build_data.py NVDA AAPL          # just these
  python3 tools/build_data.py --max-minutes 30   # stop early (the next run picks up the rest)

Writes docs/data/{TICKER}.json (schema v2) =
  {"ticker", "name", "v": 2,
   "quarter": {"ticker", "company", "period", "cik", "series": [trend points], "periods": [records]},
   "annual":  {... the same for fiscal years}}
"periods" holds the last 8 quarters / 5 fiscal years, oldest first, each a fetch_sec.py record without
its "trend"; "series" holds the trend points they share (enough for each period's own 8-quarter /
5-year window). render.period_record(block, period_end) rebuilds the full fetch_sec.py record.
Segments of a period already in the old file (same accession) are reused, so a nightly run only
downloads filings it has not seen.
Also writes docs/data/tickers.json = [[ticker, name], ...] for the search box. A ticker that fails keeps its
previous file; one failure never stops the run. Files are rewritten only when their content changes.
Set SEC_USER_AGENT to "name email" (SEC requires a contact); requests stay under SEC's 10/s limit.
"""
import argparse, json, os, sys, time
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "earnings-card", "scripts"))
os.environ.setdefault("SEC_USER_AGENT", "earnings-card (github.com/TTNAN/earnings-card) thnssssss7@gmail.com")
import fetch_sec  # noqa: E402

OUT = os.path.join(ROOT, "docs", "data")


def tickers_from_file(path):
    out = []
    for line in open(path, encoding="utf-8"):
        t = line.split("#")[0].strip().upper()
        if t and t not in out:
            out.append(t)
    return out


KEEP = {"quarter": 8, "annual": 5}
BLOCK_KEYS = ("ticker", "company", "period", "cik")


def _round(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


def slim(d):
    """Drop fields the cards never read, to keep the files small."""
    d = dict(d)
    for k in ("segments_error",):
        d.pop(k, None)
    seg = {}
    for kind, items in (d.get("segments") or {}).items():
        seg[kind] = [{k: i.get(k) for k in ("label", "value", "share", "yoy")} for i in items]
    d["segments"] = seg
    return d


def write_if_changed(path, obj):
    new = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == new:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return True


# A "latest" period older than this means the company moved its revenue to a tag we don't read
# (or stopped filing): better no card than a stale one presented as the latest.
MAX_AGE_DAYS = {"quarter": 270, "annual": 550}


def build_block(t, period, old=None):
    """The {series, periods} block for one ticker and period type. old: this block from the previous file."""
    from segments import segments
    ctx = fetch_sec.load(t, period)
    ends = sorted(ctx["s"]["revenue"])
    age = (date.today() - date.fromisoformat(ends[-1])).days
    if age > MAX_AGE_DAYS[period]:
        raise SystemExit(f"latest period {ends[-1]} is stale, skipped")
    prev = {(p["period_end"], p.get("accn")): p for p in ((old or {}).get("periods") or [])}
    recs, series = [], {}
    for e in ends[-KEEP[period]:]:
        d = fetch_sec.record(ctx, e, with_segments=False)
        hit = prev.get((e, d["accn"]))
        if hit is not None and "segments" in hit:
            d["segments"] = hit["segments"]
        else:
            try:
                d["segments"] = segments(d["cik"], d["accn"], d["period_start"], e, period == "annual") if d["accn"] else {}
            except Exception:   # a bonus; never fail the card for it
                d["segments"] = {}
        d = slim(d)
        for p in d.pop("trend"):
            series[p["end"]] = p
        recs.append(d)
    block = {k: recs[-1][k] for k in BLOCK_KEYS}
    for d in recs:
        for k in BLOCK_KEYS + ("source",):
            d.pop(k, None)
    block["series"] = [series[e] for e in sorted(series)]
    block["periods"] = recs
    return _round(block)


def build_one(t, old=None):
    rec, errors = {"ticker": t, "v": 2}, []
    for period in ("quarter", "annual"):
        try:
            o = (old or {}).get(period)
            rec[period] = build_block(t, period, o if o and "periods" in o else None)
            rec["name"] = rec[period]["company"]
        except SystemExit as e:
            errors.append(f"{period}: {e}")
        except Exception as e:  # network hiccup, odd filing: skip, keep going
            errors.append(f"{period}: {type(e).__name__}: {e}")
    return rec, errors


def index(out_dir):
    rows = []
    for f in sorted(os.listdir(out_dir)):
        if f.endswith(".json") and f != "tickers.json" and f[:-5].isupper():
            d = json.load(open(os.path.join(out_dir, f), encoding="utf-8"))
            if d.get("quarter") or d.get("annual"):
                name = d.get("name", "")
                rows.append([d["ticker"], name.title() if name.isupper() else name])
    write_if_changed(os.path.join(out_dir, "tickers.json"), rows)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--list", default=os.path.join(ROOT, "tools", "tickers.txt"))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--max-minutes", type=float, default=0, help="stop starting new tickers after this long")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    todo = [t.upper() for t in a.tickers] or tickers_from_file(a.list)
    start, ok, changed, failed = time.time(), 0, 0, []
    for i, t in enumerate(todo):
        if a.max_minutes and time.time() - start > a.max_minutes * 60:
            print(f"time limit reached, {len(todo) - i} tickers left for the next run")
            break
        path = os.path.join(a.out, f"{t.replace('.', '-')}.json")
        try:
            old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None
        except ValueError:
            old = None
        rec, errors = build_one(t, old)
        if rec.get("quarter") or rec.get("annual"):
            ok += 1
            if write_if_changed(path, rec):
                changed += 1
        else:
            failed.append(t)
        status = "ok" if not errors else ("partial" if (rec.get("quarter") or rec.get("annual")) else "FAILED")
        print(f"[{i+1}/{len(todo)}] {t}: {status}" + (f" ({'; '.join(errors)})" if errors else ""), flush=True)
    rows = index(a.out)
    print(f"done: {ok} ok, {changed} changed, {len(failed)} failed {failed if failed else ''}; {len(rows)} tickers in index")
    return 0 if ok or not todo else 1


if __name__ == "__main__":
    sys.exit(main())
