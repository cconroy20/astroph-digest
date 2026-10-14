"""Resolve every Zotero item to an ADS record -> data/library.json.

Routes: bibcode in url -> DOI -> title(+year) search, each title-verified.
"""
import json, os, re, difflib
from ads import query, arxiv_id

D = os.path.join(os.path.dirname(__file__), "..", "data")
L = json.load(open(os.path.join(D, "library_zotero.json")))
BIB = re.compile(r"\d{4}[A-Za-z][A-Za-z0-9&.]{13}[A-Z.]")


def norm(t):
    t = re.sub(r"<[^>]+>|&[a-z]+;|\$|\\[a-z]+", " ", t or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def tsim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def batched(xs, n=40):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def fetch(clauses):
    """OR together a list of clauses; return docs."""
    return query(" OR ".join(clauses), rows=2000)["docs"] if clauses else []


rec = {}  # zotero key -> ads doc
# 1. bibcode in url
by_bib = {}
for o in L:
    m = BIB.search(o["url"]) if "adsabs" in o["url"] else None
    if m:
        by_bib.setdefault(m.group(0).replace("%26", "&"), []).append(o["key"])
for chunk in batched(list(by_bib)):
    for d in fetch([f'identifier:"{b}"' for b in chunk]):
        ids = set(d.get("identifier", [])) | {d["bibcode"]}
        for b in chunk:
            if b in ids:
                for k in by_bib[b]:
                    rec[k] = d

# 2. DOI
by_doi = {}
for o in L:
    if o["key"] not in rec and o["doi"]:
        by_doi.setdefault(o["doi"].lower().strip(), []).append(o["key"])
for chunk in batched(list(by_doi)):
    clauses = ['doi:"%s"' % x.replace('"', "") for x in chunk]
    for d in fetch(clauses):
        for x in d.get("doi", []):
            for k in by_doi.get(x.lower(), []):
                rec.setdefault(k, d)

# 3. title search for the rest
zk = {o["key"]: o for o in L}
for o in L:
    if o["key"] in rec or not o["title"]:
        continue
    words = [w for w in norm(o["title"]).split() if len(w) > 3][:10]
    if not words:
        continue
    q = "title:(" + " ".join(words) + ")"
    yr = (re.search(r"\d{4}", o["date"]) or [None])[0]
    if yr:
        q += f" year:{int(yr)-1}-{int(yr)+1}"
    try:
        docs = query(q, rows=10, sort="score desc")["docs"]
    except RuntimeError as e:
        print("ERR", e)
        continue
    best = max(docs, key=lambda d: tsim(o["title"], (d.get("title") or [""])[0]), default=None)
    if best and tsim(o["title"], best["title"][0]) > 0.85:
        rec[o["key"]] = best

# verify every route by title similarity; flag weak matches
out, weak = [], []
for o in L:
    d = rec.get(o["key"])
    s = tsim(o["title"], (d.get("title") or [""])[0]) if d else 0
    if d and s < 0.6:
        weak.append((round(s, 2), o["title"][:70], d["title"][0][:70]))
    out.append({**o, "ads": d, "title_sim": round(s, 3)})
json.dump(out, open(os.path.join(D, "library.json"), "w"), indent=1)

n = len(L)
res = sum(1 for o in out if o["ads"])
print(f"resolved {res}/{n}")
print("with abstract (ADS or Zotero):", sum(1 for o in out if (o["ads"] and o["ads"].get("abstract")) or o["abstract"]))
print("with arXiv id:", sum(1 for o in out if o["ads"] and arxiv_id(o["ads"])))
print("weak title matches:", len(weak))
for w in weak[:40]:
    print("  ", w)
print("unresolved:")
for o in out:
    if not o["ads"]:
        print("  ", o["type"], "|", o["title"][:80], "|", o["date"][:4])
