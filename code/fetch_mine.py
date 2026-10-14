"""Charlie's ADS publication list and the papers he cited since 2020.

-> data/my_papers_ads.json  (orcid or name match, astronomy collection)
-> data/cited_ads.json      (references of his 2020+ papers with him among the first 3 authors; n_cited = how many cite it)
"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from ads import query_all, bigquery, FL

D = os.path.join(os.path.dirname(__file__), "..", "data")
ORCID = "0000-0002-1590-8551"

docs = query_all(f'(orcid:{ORCID} OR author:"Conroy, Charlie") collection:astronomy '
                 'doctype:(article OR eprint OR inproceedings)', fl=FL + ",reference,author_count")
json.dump(docs, open(os.path.join(D, "my_papers_ads.json"), "w"))


def pos(d):
    return next((i + 1 for i, n in enumerate(d["author"]) if n.lower().startswith("conroy, c")), 99)


src = [d for d in docs if int(d["year"]) >= 2020 and pos(d) <= 3]
C = collections.Counter()
for d in src:
    C.update(set(d.get("reference", [])))
recs = {x["bibcode"]: x for x in bigquery(list(C))}
json.dump([{**recs[b], "n_cited": C[b]} for b in recs], open(os.path.join(D, "cited_ads.json"), "w"))
print(f"{len(docs)} own papers; {len(src)} since 2020 with Conroy in first 3; {len(recs)} cited papers")
