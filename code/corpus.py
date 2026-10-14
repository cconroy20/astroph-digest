"""Merge positives (library, own papers, cited papers) -> data/positives.json.

One row per paper (keyed by ADS bibcode, or zot:KEY when unresolved). Each row keeps
the date it could first have been known (`t_known`) so the replay test can drop
anything from the future:
  lib    -> publication date (Zotero dateAdded is useless: all 2026 bulk import)
  own    -> publication date
  cited  -> pubdate of Charlie's earliest paper that cites it
"""
import json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(__file__))
from ads import arxiv_id

D = os.path.join(os.path.dirname(__file__), "..", "data")


def clean(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()


def pubdate(d):
    p = (d.get("pubdate") or d.get("year", "1900") + "-01")[:7].replace("-00", "-01")
    return p + "-01" if len(p) == 7 else p


def is_conroy(name):
    return name.lower().startswith("conroy, c")


rows = {}


def add(key, src, d=None, z=None, **extra):
    r = rows.get(key)
    if r is None:
        title = clean((d.get("title") or [""])[0] if d else z["title"])
        abstract = clean((d or {}).get("abstract", "")) or clean((z or {}).get("abstract", ""))
        if z and len(clean(z.get("abstract", ""))) > len(abstract):
            abstract = clean(z["abstract"])
        authors = (d or {}).get("author") or [
            f"{a['last']}, {a['first']}".strip(", ") for a in (z or {}).get("authors", []) if a["type"] == "author"]
        r = rows[key] = {
            "key": key, "title": title, "abstract": abstract, "authors": authors,
            "arxiv": arxiv_id(d) if d else None,
            "date": pubdate(d) if d else ((re.search(r"\d{4}", z["date"]) or ["1900"])[0] + "-01-01"),
            "doctype": (d or {}).get("doctype", (z or {}).get("type")),
            "collections": [], "src": [], "t_known": "9999",
        }
    if src not in r["src"]:
        r["src"].append(src)
    for k, v in extra.items():
        if k == "collections":
            r["collections"] = sorted(set(r["collections"]) | set(v))
        elif k == "t_known":
            r["t_known"] = min(r["t_known"], v)
        else:
            r[k] = v


# library
for o in json.load(open(os.path.join(D, "library.json"))):
    d = o["ads"]
    if d and o["title_sim"] < 0.6:
        a, b = re.sub(r"\W+", " ", o["title"].lower()), re.sub(r"\W+", " ", d["title"][0].lower())
        if not (a.startswith(b.strip()) or b.startswith(a.strip())):
            d = None  # wrong link (e.g. bad DOI in Zotero) -> fall back to Zotero metadata
    key = d["bibcode"] if d else "zot:" + o["key"]
    add(key, "lib", d, o, collections=o["collections"], zkey=o["key"],
        t_known=pubdate(d) if d else (re.search(r"\d{4}", o["date"]) or ["1900"])[0] + "-01-01")

# own papers (drop the two pre-2004 misattributions)
own = [d for d in json.load(open(os.path.join(D, "my_papers_ads.json"))) if int(d["year"]) >= 2004]
for d in own:
    pos = next((i + 1 for i, n in enumerate(d["author"]) if is_conroy(n)), 99)
    add(d["bibcode"], "own", d, own_pos=pos, n_auth=len(d["author"]), t_known=pubdate(d))

# cited by own papers since 2020 with Conroy in first 3 authors
citer_date = {}
for d in own:
    pos = next((i + 1 for i, n in enumerate(d["author"]) if is_conroy(n)), 99)
    if int(d["year"]) >= 2020 and pos <= 3:
        for b in set(d.get("reference", [])):
            citer_date[b] = min(citer_date.get(b, "9999"), pubdate(d))
for d in json.load(open(os.path.join(D, "cited_ads.json"))):
    add(d["bibcode"], "cited", d, n_cited=d["n_cited"], t_known=citer_date.get(d["bibcode"], pubdate(d)))

out = list(rows.values())
for r in out:
    r["t_known"] = max(r["t_known"], r["date"])  # cannot be known before it was published
json.dump(out, open(os.path.join(D, "positives.json"), "w"))
from collections import Counter
print(len(out), "positives;", Counter("+".join(sorted(r["src"])) for r in out).most_common())
print("no abstract:", sum(1 for r in out if not r["abstract"]))
