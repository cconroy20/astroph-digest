"""Parse harvested OAI pages -> data/astroph.json (primary astro-ph only, one row per paper).

Adds `mailing`: the date of the arXiv announcement that carried the paper as a new
submission, reconstructed from the v1 timestamp and the 14:00 ET cutoff
(Fri 14:00 -> Mon 14:00 goes out Monday). Holidays are ignored.
"""
import glob, html, json, os, re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

D = os.path.join(os.path.dirname(__file__), "..", "data")
ET = ZoneInfo("America/New_York")


def tag(rec, name):
    m = re.search(rf"<{name}>(.*?)</{name}>", rec, re.S)
    return html.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else ""


def mailing(dt_utc):
    t = dt_utc.astimezone(ET)
    d = t.date()
    if t.weekday() < 5 and t.hour < 14:
        return d
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def parse_pages(paths):
    rows = {}
    for p in paths:
        txt = open(p).read()
        for rec in txt.split("<record>")[1:]:
            if 'status="deleted"' in rec[:400]:
                continue
            cats = tag(rec, "categories").split()
            if not cats or not cats[0].startswith("astro-ph"):
                continue
            vers = re.findall(r'<version version="v(\d+)">\s*<date>([^<]+)</date>', rec)
            if not vers:
                continue
            v1 = parsedate_to_datetime(dict(vers)["1"] if "1" in dict(vers) else vers[0][1]).astimezone(timezone.utc)
            aid = tag(rec, "id")
            rows[aid] = {
                "id": aid, "title": tag(rec, "title"), "authors": tag(rec, "authors"),
                "abstract": tag(rec, "abstract"), "cats": cats, "primary": cats[0],
                "v1": v1.isoformat(), "mailing": mailing(v1).isoformat(),
                "comments": tag(rec, "comments"), "journal": tag(rec, "journal-ref"),
                "doi": tag(rec, "doi"), "nver": len(vers),
            }
    return rows


if __name__ == "__main__":
    rows = parse_pages(sorted(glob.glob(os.path.join(D, "oai", "p*.xml"))))
    out = sorted(rows.values(), key=lambda r: r["v1"])
    json.dump(out, open(os.path.join(D, "astroph.json"), "w"))
    print(len(out), "primary astro-ph papers")
    # small table the daily job needs (the full record is too big to ship): author key -> paper count, keys seen twice+
    from authors import field_counts
    fc = {k: v for k, v in field_counts(out).items() if v >= 2}
    json.dump({"n_papers": len(out), "counts": fc}, open(os.path.join(D, "field_authors.json"), "w"))
    print(len(fc), "author keys -> data/field_authors.json")
