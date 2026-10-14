"""Minimal ADS API helper."""
import os, time, requests

TOKEN = open(os.path.expanduser("~/.ads/dev_key")).read().strip()
URL = "https://api.adsabs.harvard.edu/v1/search/query"
FL = "bibcode,title,abstract,author,doi,identifier,pubdate,year,keyword,doctype,arxiv_class,pub,citation_count,orcid_pub,orcid_user,orcid_other"


def query(q, fl=FL, rows=2000, start=0, sort="date desc", fq=None):
    params = {"q": q, "fl": fl, "rows": rows, "start": start, "sort": sort}
    if fq:
        params["fq"] = fq
    for attempt in range(5):
        r = requests.get(URL, params=params, headers={"Authorization": "Bearer " + TOKEN}, timeout=60)
        if r.status_code == 200:
            return r.json()["response"]
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (attempt + 1))
            continue
        raise RuntimeError(f"ADS {r.status_code}: {r.text[:300]} | q={q[:200]}")
    raise RuntimeError("ADS retries exhausted")


def query_all(q, fl=FL, sort="date desc", fq=None, maxrows=100000):
    docs, start = [], 0
    while True:
        res = query(q, fl=fl, rows=2000, start=start, sort=sort, fq=fq)
        docs += res["docs"]
        start += len(res["docs"])
        if start >= res["numFound"] or not res["docs"] or start >= maxrows:
            return docs


def arxiv_id(doc):
    for ident in doc.get("identifier", []):
        if ident.startswith("arXiv:"):
            return ident[6:]
    return None


def bigquery(bibcodes, fl=FL):
    """Fetch records for up to ~2000 bibcodes per call via the bigquery endpoint."""
    out = []
    for i in range(0, len(bibcodes), 2000):
        chunk = bibcodes[i:i + 2000]
        for attempt in range(5):
            r = requests.post(URL.replace("query", "bigquery"),
                              params={"q": "*:*", "fl": fl, "rows": 2000},
                              headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "big-query/csv"},
                              data="bibcode\n" + "\n".join(chunk), timeout=120)
            if r.status_code == 200:
                out += r.json()["response"]["docs"]
                break
            time.sleep(5 * (attempt + 1))
        else:
            raise RuntimeError(f"bigquery {r.status_code}: {r.text[:300]}")
    return out
