#!/usr/bin/env python3
"""Find the earnings press releases (8-K Item 2.02, exhibit 99.1) and pull their outlook text.

The press release that announced this quarter carries the outlook for NEXT quarter.
The one before it carried the outlook for THIS quarter, so we can check it against actuals.
Outlook wording differs by company, so this script only extracts the text; the agent reads it
and writes guidance.json (see SKILL.md).

Usage: python3 fetch_guidance.py data.json --out guidance_raw.json
"""
import argparse, html, json, re
from datetime import date

from fetch_sec import _get, _get_raw

KEYS = re.compile(r"\b(outlook|guidance|expects?|expected to be|anticipates?)\b", re.I)
HEAD = re.compile(r"\n\s*(outlook|business outlook|financial outlook|guidance|"
                  r"(first|second|third|fourth)[- ]quarter (fiscal )?(year )?(\d{4} )?(outlook|guidance))\s*\n", re.I)


def _text(raw):
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d|table)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s)


def _outlook(text):
    m = HEAD.search(text)
    if m:
        return text[m.start():m.start() + 3000].strip()
    # no heading: keep the sentences that talk about the future and carry numbers
    sents = re.split(r"(?<=[.;])\s+", text)
    hits = [x for x in sents if KEYS.search(x) and re.search(r"\$\s?\d|\d+(\.\d+)?\s?%", x)
            and not re.search(r"forward-looking|safe harbor|risks and uncertainties", x, re.I)]
    return " ".join(hits)[:3000]


def _release(cik, accn):
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}"
    idx = json.loads(_get_raw(folder + "/index.json", f"idx-{accn}.json"))
    names = [x["name"] for x in idx["directory"]["item"]]
    cands = [n for n in names if re.search(r"ex-?99|exhibit99|ex991|pr\.htm|press", n, re.I) and n.endswith((".htm", ".html"))]
    if not cands:
        return None
    name = sorted(cands, key=lambda n: (not re.search(r"99[-_.]?1|991", n), n))[0]
    url = f"{folder}/{name}"
    text = _text(_get_raw(url, f"ex99-{accn}.htm"))
    return {"url": url, "outlook_text": _outlook(text)}


def guidance_raw(d):
    sub = _get(f"https://data.sec.gov/submissions/CIK{int(d['cik']):010d}.json", f"sub-{d['cik']}.json", max_age=6 * 3600)
    r = sub["filings"]["recent"]
    end = date.fromisoformat(d["period_end"])
    rel = [(r["filingDate"][i], r["accessionNumber"][i]) for i in range(len(r["form"]))
           if r["form"][i] == "8-K" and "2.02" in (r["items"][i] or "")]
    rel.sort()
    after = [x for x in rel if 0 <= (date.fromisoformat(x[0]) - end).days <= 75]
    if not after:
        return {"current": None, "prior": None, "note": "no earnings 8-K found for this quarter"}
    cur = after[0]
    before = [x for x in rel if x[0] < cur[0]]
    out = {"current": None, "prior": None}
    for key, x in (("current", cur), ("prior", before[-1] if before else None)):
        if x:
            info = _release(d["cik"], x[1]) or {}
            out[key] = {"filed": x[0], "accn": x[1], **info}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--out", default="guidance_raw.json")
    a = ap.parse_args()
    d = json.load(open(a.data))
    res = guidance_raw(d)
    json.dump(res, open(a.out, "w"), indent=2, ensure_ascii=False)
    for k in ("current", "prior"):
        v = res.get(k) or {}
        print(f"== {k}: {v.get('filed')} {v.get('url')}\n{(v.get('outlook_text') or '(none)')[:1500]}\n")
