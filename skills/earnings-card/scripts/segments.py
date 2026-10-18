#!/usr/bin/env python3
"""Revenue by segment / product / geography, read from the filing's own XBRL instance.

SEC's companyfacts API drops dimensional facts, so this downloads the 10-Q/10-K instance
(<name>_htm.xml) and its label file, then keeps 3-month (or full-year) revenue facts with exactly one dimension.

Usage: python3 segments.py <cik> <accession-number> <period_start> <period_end>
Library: from segments import segments; segments(cik, accn, start, end) -> dict
"""
import json, re, sys, itertools
import xml.etree.ElementTree as ET
from datetime import date

from fetch_sec import _get_raw, _days

REV_TAGS = {"Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax", "RevenuesNetOfInterestExpense"}
AXES = {
    "srt:ProductOrServiceAxis": "product",
    "us-gaap:StatementBusinessSegmentsAxis": "segment",
    "srt:StatementGeographicalAxis": "geo",
    "us-gaap:StatementGeographicalAxis": "geo",
}
GEO_NAMES = {"country:US": "United States", "country:CN": "China", "country:TW": "Taiwan", "country:JP": "Japan",
             "country:DE": "Germany", "country:GB": "United Kingdom", "country:IN": "India", "country:KR": "South Korea",
             "country:SG": "Singapore", "country:IE": "Ireland", "country:CA": "Canada", "country:FR": "France",
             "srt:AmericasMember": "Americas", "srt:EuropeMember": "Europe", "srt:AsiaPacificMember": "Asia Pacific",
             "us-gaap:NonUsMember": "Outside US", "srt:NorthAmericaMember": "North America",
             "srt:LatinAmericaMember": "Latin America"}


def _pretty(qname):
    name = qname.split(":")[-1]
    name = re.sub(r"(Member|Segment)$", "", name)
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", name).strip()


def _clean(label):
    import html as _h
    label = _h.unescape(label).strip()
    label = re.sub(r"\s+(segment|Segment|segments)$", "", label)
    if label.isupper() and len(label) > 3 and label not in {"EMEA", "APAC", "LATAM", "AMEA", "EMEIA"}:
        label = label.title()
    return label


def _labels(lab_xml):
    out = {}
    pat = re.compile(r'xlink:label="lab_([A-Za-z0-9\-]+)_([A-Za-z0-9_]+?)"[^>]*xlink:role="[^"]*/role/(terseLabel|label)"[^>]*>([^<]+)<')
    for prefix, name, role, text in pat.findall(lab_xml):
        key = f"{prefix}:{name}"
        text = re.sub(r"\s*\[Member\]$", "", text.strip())
        if role == "terseLabel" or key not in out:
            out[key] = text
    return out


def _pick_partition(items, total):
    """Members can overlap (subtotals). Pick the smallest non-overlapping set (>=2) that sums to the total."""
    items = [i for i in items if i["value"] > 0]
    if total:
        items = [i for i in items if i["value"] < total * 0.999]
    if len(items) < 2:
        return []
    if not total:
        return sorted(items, key=lambda i: -i["value"])
    best = None
    n = len(items)
    if n > 16:
        items = sorted(items, key=lambda i: -i["value"])[:16]
        n = 16
    # most granular exact partition wins (iPhone/Mac/iPad/... beats Products/Services), capped at 8 rows
    for k in range(min(n, 8), 1, -1):
        for combo in itertools.combinations(items, k):
            ssum = sum(i["value"] for i in combo)
            if abs(ssum - total) <= total * 0.005:
                best = combo
                break
        if best:
            break
    if not best:
        # no exact partition: show the members as reported, largest first, plus "Other" if they fall short
        top = sorted(items, key=lambda i: -i["value"])
        acc, chosen = 0, []
        for i in top:
            if acc + i["value"] <= total * 1.005:
                chosen.append(i)
                acc += i["value"]
        if len(chosen) >= 2 and total - acc > total * 0.01:
            chosen.append({"member": "other", "label": "Other", "value": total - acc, "prev": None})
        best = chosen if len(chosen) >= 2 else None
    return sorted(best, key=lambda i: -i["value"]) if best else []


def segments(cik, accn, start, end, yearly=False):
    """yearly=True reads full fiscal-year facts (10-K) instead of 3-month ones."""
    lo_d, hi_d = (350, 380) if yearly else (80, 100)
    folder = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}"
    idx = json.loads(_get_raw(folder + "/index.json", f"idx-{accn}.json"))
    names = [x["name"] for x in idx["directory"]["item"]]
    inst = next((n for n in names if n.endswith("_htm.xml")), None) or \
        next((n for n in names if n.endswith(".xml") and not re.search(r"_(cal|def|lab|pre)\.xml$|FilingSummary", n)), None)
    if not inst:
        return {}
    lab = next((n for n in names if n.endswith("_lab.xml")), None)
    root = ET.fromstring(_get_raw(f"{folder}/{inst}", f"inst-{accn}.xml"))
    labels = _labels(_get_raw(f"{folder}/{lab}", f"lab-{accn}.xml").decode("utf-8", "ignore")) if lab else {}

    X, DI = "{http://www.xbrl.org/2003/instance}", "{http://xbrl.org/2006/xbrldi}"
    ctx = {}
    for c in root.findall(X + "context"):
        p = c.find(X + "period")
        s, e = p.find(X + "startDate"), p.find(X + "endDate")
        mem = [(m.get("dimension"), m.text.strip()) for m in c.iter(DI + "explicitMember")]
        typed = list(c.iter(DI + "typedMember"))
        ctx[c.get("id")] = (s.text if s is not None else None, e.text if e is not None else None, mem, bool(typed))

    prev_end = date.fromisoformat(end).replace(year=date.fromisoformat(end).year - 1).isoformat()
    cur, prev, totals = {}, {}, {}
    for el in root:
        tag = el.tag.split("}")[-1]
        if tag not in REV_TAGS or el.text is None:
            continue
        s, e, mem, typed = ctx.get(el.get("contextRef"), (None, None, [], True))
        if not s or typed or not (lo_d <= _days(s, e) <= hi_d):
            continue
        is_cur = abs(_days(e, end)) <= 7
        is_prev = abs(_days(e, prev_end)) <= 7
        if not (is_cur or is_prev):
            continue
        v = float(el.text)
        if not mem:
            totals.setdefault("cur" if is_cur else "prev", {})[tag] = v
            continue
        # ignore the "operating segments" consolidation marker that some filers add as a second dimension
        mem = [m for m in mem if not (m[0] == "srt:ConsolidationItemsAxis" and m[1] == "us-gaap:OperatingSegmentsMember")]
        if len(mem) != 1 or mem[0][0] not in AXES:
            continue
        key = (AXES[mem[0][0]], mem[0][1], tag)
        (cur if is_cur else prev)[key] = v

    total_cur = max((totals.get("cur") or {0: 0}).values())
    result = {}
    for kind in ("product", "segment", "geo"):
        tags = {k[2] for k in cur if k[0] == kind}
        if not tags:
            continue
        tag = max(tags, key=lambda tg: sum(1 for k in cur if k[0] == kind and k[2] == tg))
        items = []
        for (kd, member, tg), v in cur.items():
            if kd != kind or tg != tag:
                continue
            label = _clean(labels.get(member) or GEO_NAMES.get(member) or _pretty(member))
            items.append({"member": member, "label": label, "value": v, "prev": prev.get((kd, member, tg))})
        total = (totals.get("cur") or {}).get(tag) or total_cur
        part = _pick_partition(items, total)
        if part:
            for i in part:
                i["share"] = i["value"] / total if total else None
                i["yoy"] = (i["value"] - i["prev"]) / abs(i["prev"]) if i.get("prev") else None
            result[kind] = part
    # A business-segment split that just repeats the product split adds nothing.
    if "product" in result and "segment" in result and \
            {round(i["value"]) for i in result["product"]} == {round(i["value"]) for i in result["segment"]}:
        result.pop("segment")
    return result


if __name__ == "__main__":
    cik, accn, start, end = sys.argv[1:5]
    print(json.dumps(segments(cik, accn, start, end), indent=2, ensure_ascii=False))
