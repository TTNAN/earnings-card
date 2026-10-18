#!/usr/bin/env python3
"""Precompute card data for the web generator (GitHub Pages can't call SEC from the browser).

  python3 tools/build_data.py                    # every ticker in tools/tickers.txt
  python3 tools/build_data.py NVDA AAPL          # just these
  python3 tools/build_data.py --max-minutes 30   # stop early (the next run picks up the rest)

Writes docs/data/{TICKER}.json = {"ticker", "name", "quarter": {...}, "annual": {...}} (fetch_sec.py schema)
and docs/data/tickers.json = [[ticker, name], ...] for the search box. A ticker that fails keeps its
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


def build_one(t):
    rec, errors = {"ticker": t}, []
    for period in ("quarter", "annual"):
        try:
            d = fetch_sec.build(t, period)
            age = (date.today() - date.fromisoformat(d["period_end"])).days
            if age > MAX_AGE_DAYS[period]:
                errors.append(f"{period}: latest period {d['period_end']} is stale, skipped")
                continue
            rec[period] = slim(d)
            rec["name"] = d["company"]
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
        rec, errors = build_one(t)
        if rec.get("quarter") or rec.get("annual"):
            ok += 1
            if write_if_changed(os.path.join(a.out, f"{t.replace('.', '-')}.json"), rec):
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
